"""Per-scene audio re-generation for Director long video.

Turbo/distilled few-step models (HyperFlow, turbo LoRAs) leave H3 audio undercooked.
After a scene is sampled, its video latent is shrunk, recombined with the scene audio
and re-sampled from the middle of the schedule with the undistilled base model; only
the new audio is kept, so the picture is untouched and speech stays in sync.
"""
import comfy.nested_tensor
import comfy.utils

from . import director_lbh


def settings(enabled=False, model=None, scale=0.5, steps=30, denoise=0.5):
    if not enabled:
        return None
    if model is None:
        raise ValueError('Director audio regen: connect audio_regen_model (the base model before HyperFlow/turbo).')
    return {'version': 1, 'scale': float(scale), 'steps': int(steps), 'denoise': float(denoise)}


def shrink(video, scale):
    """Downscale a [B,C,T,H,W] video latent, keeping even spatial sizes for H3 patchify."""
    height = max(2, round(video.shape[-2] * scale / 2) * 2)
    width = max(2, round(video.shape[-1] * scale / 2) * 2)
    return comfy.utils.common_upscale(video, width, height, 'bilinear', 'disabled')


def regenerate(model, base_positive, sampled, context_proxy, motion, context_length, audio_context_length,
               base_width, base_height, vae, seed, sampler_name, config, sample, context_decode_cache=None):
    video, audio = sampled['samples'].unbind()
    small = shrink(video, config['scale'])
    width, height = small.shape[-1] * 16, small.shape[-2] * 16
    latent = {'samples': comfy.nested_tensor.NestedTensor((small, audio))}
    positive = director_lbh.resize_conditioning(base_positive, base_width, base_height, width, height, vae)
    if context_proxy is not None:
        context = director_lbh.resize_context(context_proxy, width, height, vae, context_decode_cache)
        positive = motion.apply(positive, latent, context, context_length, audio_context_length)[0]
    out = sample(model, positive, latent, seed, sampler_name, 'simple', config['steps'], config['denoise'])
    _, new_audio = out['samples'].unbind()
    if new_audio.shape != audio.shape:
        raise ValueError('Director audio regen: audio latent layout changed.')
    result = dict(sampled)
    result['samples'] = comfy.nested_tensor.NestedTensor((video, new_audio.to(audio.device, audio.dtype)))
    return result
