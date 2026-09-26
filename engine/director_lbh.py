"""LBH spatial upscale for Director's two-pass AV sampling path."""
import math

import comfy.nested_tensor
import comfy.utils
import nodes
import folder_paths


def settings(enabled=False, scale=1.5, model_name='minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors'):
    if not enabled:
        return None
    scale = float(scale)
    if not math.isfinite(scale) or not 1.0 <= scale <= 4.0:
        raise ValueError('Director LBH: scale must be between 1 and 4.')
    if 'MinimaxH3LatentUpscaler3D' not in nodes.NODE_CLASS_MAPPINGS:
        raise ValueError('Director LBH: install Comfyui_Minimax_h3_latent_Upscaler first.')
    if not folder_paths.get_full_path('latent_upscale_models', model_name):
        raise ValueError(f'Director LBH: missing model in models/latent_upscale_models: {model_name}')
    return {'version': 1, 'scale': scale, 'model_name': str(model_name), 'refine_steps': 4}


def output_size(width, height, config):
    if not config:
        return width, height
    return tuple(max(32, round(x * config['scale'] / 32) * 32) for x in (width, height))


def resize_context(context, width, height):
    """Only the low-resolution pass sees a resized copy of the previous scene."""
    if context is None:
        return None
    video, audio = context['samples'].unbind()
    video = comfy.utils.common_upscale(video, width // 16, height // 16, 'bilinear', 'disabled')
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


def resize_conditioning(conditioning, base_width, base_height, width, height):
    """Resize visual reference blocks; preserve audio and temporal coordinates."""
    result = []
    for embedding, metadata in conditioning:
        metadata = dict(metadata)
        for key in ('minimax_refs', 'minimax_keyframes'):
            if key not in metadata:
                continue
            blocks = []
            for block in metadata[key]:
                block = dict(block)
                z = block.get('latent')
                if z is not None and block.get('kind') != 'audio':
                    if key == 'minimax_keyframes':
                        tw, th = width // 16, height // 16
                    else:
                        tw = max(2, round(z.shape[-1] * width / base_width / 2) * 2)
                        th = max(2, round(z.shape[-2] * height / base_height / 2) * 2)
                    block['latent'] = comfy.utils.common_upscale(z, tw, th, 'bilinear', 'disabled')
                    if 'latent_h' in block:
                        block.update(latent_h=th, latent_w=tw)
                blocks.append(block)
            metadata[key] = blocks
        result.append([embedding, metadata])
    return result
