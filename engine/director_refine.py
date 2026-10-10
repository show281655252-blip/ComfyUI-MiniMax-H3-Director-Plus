"""Long video (experimental): refresh each continued scene with a short resample.

Chained Motion Context scenes take the previous scene's tail as ground truth, so small
losses add up ("photocopy effect"): characters turn waxy / burnt after several scenes.
Idea from xyzDist/H3-LongTakeNoCuts (also used in the Arca "Minimax_Longform" workflow):
after a continued scene is sampled, sample it again at denoise ~0.55 for a few steps with
the same conditioning, then cross-fade the video from the original to the refined result
over [context, 2 x context] frames. The inherited context frames stay as generated (the
seam keeps matching the previous scene) and the next scene inherits the refined tail.
Audio is kept from the original sample. The first scene has no inherited context and is
left as is, like the reference workflow.
"""
import comfy.nested_tensor
import torch


def settings(value):
    """long_video.refine from the scene timeline -> engine config, or None when off."""
    if not isinstance(value, dict) or not value.get("enabled"):
        return None
    steps = max(1, min(20, int(value.get("steps", 4))))
    denoise = max(0.05, min(1.0, float(value.get("denoise", 0.55))))
    return {"version": 1, "steps": steps, "denoise": denoise}


def blend_weights(latent_frames, pixel_frames, start, end, device):
    """Per latent frame weight of the refined video: 0 before `start`, 1 after `end` (pixel frames)."""
    pos = torch.arange(latent_frames, dtype=torch.float32, device=device) * (float(pixel_frames) / latent_frames)
    if end <= start:
        return (pos >= start).float()
    return ((pos - start) / float(end - start)).clamp(0.0, 1.0)


def refine(model, positive, sampled, seed, sampler_name, pixel_frames, trim_frames, config, sample):
    """Return (latent, report). `sample` is the engine's _sample_h3."""
    trim = int(trim_frames or 0)
    if trim <= 0:
        return sampled, "skipped (no inherited context)"
    video, audio = sampled["samples"].unbind()
    out = sample(model, positive, sampled, seed, sampler_name, "simple", config["steps"], config["denoise"])
    refined = out["samples"].unbind()[0].to(video.device, video.dtype)
    if refined.shape != video.shape:
        raise ValueError("Director refine: video latent layout changed.")
    w = blend_weights(video.shape[2], pixel_frames, trim, 2 * trim, video.device)
    w = w.view(1, 1, -1, 1, 1).to(video.dtype)
    mixed = video * (1 - w) + refined * w
    result = dict(sampled)
    result["samples"] = comfy.nested_tensor.NestedTensor((mixed, audio))
    return result, (f"{config['steps']} steps, denoise {config['denoise']:.2f}, "
                    f"original until frame {trim}, refined from frame {2 * trim}, audio kept")
