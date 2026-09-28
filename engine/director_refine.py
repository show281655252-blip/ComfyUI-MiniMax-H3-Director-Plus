"""Opt-in adapter for the separately installed ComfyUI-H3-Refine package."""
import hashlib
import inspect
from pathlib import Path

from . import director_lbh


def settings(enabled=False, steps=2):
    if not enabled:
        return None
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get('H3RefinePass')
    if cls is None:
        raise ValueError('Director Refine: install ComfyUI-H3-Refine and restart ComfyUI first.')
    steps = int(steps)
    if not 1 <= steps <= 20:
        raise ValueError('Director Refine: steps must be between 1 and 20.')
    # A pack update must not silently reuse a result from different refine code.
    directory = Path(inspect.getfile(cls)).parent
    digest = hashlib.sha256()
    for name in ('nodes.py', 'schedule.py', 'latents.py', 'refine_blend.py'):
        digest.update((directory / name).read_bytes())
    return {'version': 2, 'steps': steps, 'align': 'hop_tail',
            'head': 'freeze', 'audio': 'freeze', 'blend': 'auto',
            'sampler': 'res_multistep', 'pack_hash': digest.hexdigest()[:16]}


def refine(model, base_positive, sampled, base_width, base_height, vae,
           seed, sigmas, trim_frames, config):
    import nodes
    import torch
    video, audio = sampled['samples'].unbind()
    positive = director_lbh.resize_conditioning(
        base_positive, base_width, base_height,
        video.shape[-1] * 16, video.shape[-2] * 16, vae)
    # Use base conditioning, never the Motion Context keyframes. The pin is
    # held/blended by H3RefinePass itself, using the actual overlap length.
    out = nodes.NODE_CLASS_MAPPINGS['H3RefinePass']().refine(
        latent=sampled, model=model, conditioning=positive,
        steps=config['steps'], denoise=0.5, sampler_name=config['sampler'],
        scheduler='simple', seed=int(seed), refine_audio='freeze',
        refine_head='freeze', pin_frames=int(trim_frames or 0),
        blend='auto', blend_interp='linear', refine_align='hop_tail',
        base_sigmas=sigmas)[0]
    new_video, new_audio = out['samples'].unbind()
    if new_video.shape != video.shape or new_audio.shape != audio.shape:
        raise ValueError(f'Director Refine: latent layout changed: {video.shape}/{audio.shape} -> {new_video.shape}/{new_audio.shape}.')
    if not torch.equal(audio, new_audio):
        delta = (audio.float() - new_audio.to(audio.device).float()).abs().max().item()
        print(f'[Director Refine] Restoring original frozen audio (sampler max delta={delta:.8g}).', flush=True)
    # A zero noise mask still passes through core latent-format transforms;
    # roundoff is possible. Preserve the actual input tensor, not a round trip.
    out = dict(out)
    out['samples'] = type(sampled['samples'])((new_video, audio))
    return out
