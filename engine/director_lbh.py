"""LBH spatial upscale for Director's two-pass AV sampling path."""
import math

import comfy.nested_tensor
import comfy.utils
import nodes
import folder_paths


def settings(enabled=False, scale=1.5, model_name='minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors',
             full_first_pass=False):
    if not enabled:
        return None
    scale = float(scale)
    if not math.isfinite(scale) or not 1.0 <= scale <= 4.0:
        raise ValueError('Director LBH: scale must be between 1 and 4.')
    if 'MinimaxH3LatentUpscaler3D' not in nodes.NODE_CLASS_MAPPINGS:
        raise ValueError('Director LBH: install Comfyui_Minimax_h3_latent_Upscaler first.')
    if not folder_paths.get_full_path('latent_upscale_models', model_name):
        raise ValueError(f'Director LBH: missing model in models/latent_upscale_models: {model_name}')
    config = {'version': 2, 'scale': scale, 'model_name': str(model_name), 'refine_steps': 4}
    if full_first_pass:
        # Run the whole schedule at base resolution, then refine with its last 4 steps (8+4).
        # Only added when on, so existing 4+4 caches keep their owner.
        config['first_pass'] = 'full'
    return config


def full_first_pass(config):
    return bool(config and config.get('first_pass') == 'full')


def output_size(width, height, config):
    if not config:
        return width, height
    return tuple(max(32, round(x * config['scale'] / 32) * 32) for x in (width, height))


def resize_context(context, width, height, vae):
    """Only the low-resolution pass sees a resized copy of the previous scene."""
    if context is None:
        return None
    video, audio = context['samples'].unbind()
    video = reencode_visual(video, width // 16, height // 16, vae)
    return {'samples': comfy.nested_tensor.NestedTensor((video, audio))}


def upscale_latent(latent, config):
    video, audio = latent['samples'].unbind()
    cls = nodes.NODE_CLASS_MAPPINGS['MinimaxH3LatentUpscaler3D']
    output = cls.execute(
        latent={'samples': video}, model_name=config['model_name'],
        mode={'mode': 'scale by multiplier', 'scale': config['scale']},
        align=32, enable_temporal_chunking=True, force_unload=True,
        device='cuda', precision='bf16',
    )
    result = dict(latent)
    result['samples'] = comfy.nested_tensor.NestedTensor((output.result[0]['samples'], audio))
    return result


def reencode_visual(latent, width, height, vae, pixels=None, crop='disabled'):
    """H3 latent channels are not pixels: spatial interpolation causes ghosting."""
    if latent.shape[-2:] == (height, width):
        return latent
    if pixels is None:
        pixels = vae.decode(latent)
    if pixels.ndim == 5 and pixels.shape[0] == 1:
        pixels = pixels[0]
    if pixels.ndim != 4:
        raise ValueError('Director LBH: expected decoded/source frames [T,H,W,C].')
    pixels = comfy.utils.common_upscale(
        pixels[..., :3].movedim(-1, 1), width * 16, height * 16,
        'bicubic', crop).movedim(1, -1).clamp(0, 1)
    result = vae.encode(pixels)
    if result.shape[:3] != latent.shape[:3] or result.shape[-2:] != (height, width):
        raise ValueError('Director LBH: re-encoding changed the temporal layout or target grid.')
    return result


def resize_conditioning(conditioning, base_width, base_height, width, height, vae, guide=None):
    """Resize visual reference blocks; preserve audio and temporal coordinates."""
    result = []
    for embedding, metadata in conditioning:
        metadata = dict(metadata)
        for key in ('minimax_refs', 'minimax_keyframes'):
            if key not in metadata:
                continue
            blocks = []
            image_index = 0
            source_images = [v for v in (guide or {}).get('ref_images', {}).values() if v is not None]
            for block in metadata[key]:
                block = dict(block)
                z = block.get('latent')
                # Long-video RefMods keep their stored (possibly compressed) grid.
                if z is not None and block.get('kind') != 'audio' and not block.get('_director_refmod'):
                    if key == 'minimax_keyframes':
                        tw, th = width // 16, height // 16
                    else:
                        tw = max(2, round(z.shape[-1] * width / base_width / 2) * 2)
                        th = max(2, round(z.shape[-2] * height / base_height / 2) * 2)
                    pixels = block.get('_director_source_pixels')
                    crop = 'disabled'
                    if key == 'minimax_refs' and block.get('kind') == 'image':
                        if pixels is None and image_index < len(source_images):
                            pixels = source_images[image_index][:1]
                        image_index += 1
                    elif key == 'minimax_keyframes' and guide:
                        frame = block.get('resolved_frame_index')
                        if frame == 0:
                            pixels = guide.get('first_frame')
                        elif frame == guide.get('length', 0) - 1:
                            pixels = guide.get('last_frame')
                            crop = 'center'
                        if pixels is not None:
                            pixels = pixels[:1]
                    block['latent'] = reencode_visual(z, tw, th, vae, pixels, crop)
                    block.pop('_director_source_pixels', None)
                    if 'latent_h' in block:
                        block.update(latent_h=th, latent_w=tw)
                blocks.append(block)
            metadata[key] = blocks
        result.append([embedding, metadata])
    return result


class DirectorPlusConditioningMatchLatent:
    """Match conditioning to the actual LBH grid, not a separately rounded scale."""

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'conditioning': ('CONDITIONING',),
            'base_latent': ('LATENT',),
            'target_latent': ('LATENT',),
            'vae': ('VAE',),
        }, 'optional': {'guide': ('MINIMAX_H3_DIRECTOR_GUIDE',)}}

    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'execute'
    CATEGORY = 'Director Plus/conditioning'

    def execute(self, conditioning, base_latent, target_latent, vae, guide=None):
        def spatial_size(latent):
            samples = latent['samples']
            if getattr(samples, 'is_nested', False):
                samples = samples.unbind()[0]
            if samples.ndim != 5 or any(s < 2 or s % 2 for s in samples.shape[-2:]):
                raise ValueError('Director Plus: expected a video latent with even spatial dimensions.')
            return int(samples.shape[-1]) * 16, int(samples.shape[-2]) * 16

        base_width, base_height = spatial_size(base_latent)
        width, height = spatial_size(target_latent)
        return (resize_conditioning(conditioning, base_width, base_height, width, height, vae, guide),)
