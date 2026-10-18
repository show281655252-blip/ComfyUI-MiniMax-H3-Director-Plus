"""Long video (experimental): refresh each continued scene with a short resample.

Chained Motion Context scenes take the previous scene's tail as ground truth, so small
losses add up ("photocopy effect"): characters turn waxy / burnt after several scenes.
Idea from xyzDist/H3-LongTakeNoCuts (also used in the Arca "Minimax_Longform" workflow):
after a continued scene is sampled, sample it again, then cross-fade the video from the
original to the refined result from the end of the inherited context onwards. Like the
author's example workflow, the resample uses the scene's own conditioning WITHOUT the
inherited-context guide (so the degraded tail is not pinned again) and its own noise seed
(scene seed + 1). The inherited context frames stay as generated (the seam keeps matching
the previous scene) and the next scene inherits the refined tail. Audio is kept from the
original sample. The first scene has no inherited context and is left as is.

Resample modes:
- "denoise": a few steps from `denoise` (the author's 0.5-0.6).
- "last_step": only the main schedule's last step again (NikoDemon80's tip: with H3's shift
  12, denoise 0.55 restarts near sigma 0.94 and redraws almost everything; one low-sigma step
  keeps the face, background and colour while still refreshing the latent).

Subject mask (LongTakeNoCuts v02): SAM3 finds the subject ("main subject" by default) on the
decoded scene; the mask is grown and feathered, ramps in after the context frames, and goes to
the sampler as noise_mask, so only the subject is redrawn and the background stays as generated.
"""
import comfy.nested_tensor
import folder_paths
import nodes
import torch
import torch.nn.functional as F

MODES = ("denoise", "last_step")
DEFAULT_PROMPT = "main subject"
SAM3_NAME = "sam3.1_multiplex_fp16"
MASK_GROW = 5        # pixels, like GrowMaskWithBlur expand 5 in the author's workflow
MASK_FEATHER = 5     # pixels, blur radius
MASK_RAMP = 8        # pixel frames after the context: subject mask 0 -> 1 (author: 22:0, 30:1)
_SAM3 = {}


def settings(value):
    """long_video.refine from the scene timeline -> engine config, or None when off."""
    if not isinstance(value, dict) or not value.get("enabled"):
        return None
    steps = max(1, min(20, int(value.get("steps", 5))))
    denoise = max(0.05, min(1.0, float(value.get("denoise", 0.55))))
    mode = value.get("mode") if value.get("mode") in MODES else "denoise"
    blend = max(1, min(120, int(value.get("blend_frames", 0) or 0))) if value.get("blend_frames") else None
    prompt = str(value.get("subject_prompt") or "").strip() or DEFAULT_PROMPT
    return {"version": 2, "steps": steps, "denoise": denoise, "mode": mode,
            "blend_frames": blend, "subject": bool(value.get("subject")), "subject_prompt": prompt}


def blend_weights(latent_frames, pixel_frames, start, end, device):
    """Per latent frame weight of the refined video: 0 before `start`, 1 after `end` (pixel frames)."""
    pos = torch.arange(latent_frames, dtype=torch.float32, device=device) * (float(pixel_frames) / latent_frames)
    if end <= start:
        return (pos >= start).float()
    return ((pos - start) / float(end - start)).clamp(0.0, 1.0)


def _sam3():
    names = [n for n in folder_paths.get_filename_list("checkpoints") if "sam3" in n.lower()]
    name = next((n for n in names if SAM3_NAME in n), names[0] if names else None)
    if name is None:
        raise ValueError("Director 이어받기 보정: 「인물만」에 필요한 SAM3 모델(sam3.1_multiplex_fp16.safetensors)이 "
                         "models/checkpoints에 없습니다.")
    if _SAM3.get("name") != name:
        model, clip, _vae = nodes.CheckpointLoaderSimple().load_checkpoint(name)[:3]
        _SAM3.clear()
        _SAM3.update(name=name, model=model, clip=clip, prompts={})
    return _SAM3


def subject_mask(vae, video, pixel_frames, trim, prompt):
    """[1,1,T,h,w] noise mask for the video latent: 1 = redraw (subject), 0 = keep. None if no subject."""
    from comfy_extras.nodes_sam3 import SAM3_Detect

    latent_t, h, w = video.shape[2], video.shape[3], video.shape[4]
    frames = vae.decode(video)
    if frames.ndim == 5:
        frames = frames[0]
    frames = frames[..., :3]
    # One detection per latent frame is enough: the mask ends up at latent resolution anyway.
    count = frames.shape[0]
    picks = [min(count - 1, round(k * count / latent_t)) for k in range(latent_t)]
    sam = _sam3()
    cond = sam["prompts"].get(prompt)
    if cond is None:
        cond = sam["prompts"][prompt] = nodes.CLIPTextEncode().encode(sam["clip"], prompt)[0]
    out = SAM3_Detect.execute(sam["model"], frames[picks], conditioning=cond, threshold=0.5, refine_iterations=2)
    masks = (out.result if hasattr(out, "result") else out)[0].float()   # [T, H, W]
    del frames
    if float(masks.max()) <= 0:
        return None, 0.0
    m = masks.unsqueeze(1)
    m = F.max_pool2d(m, 2 * MASK_GROW + 1, stride=1, padding=MASK_GROW)
    m = F.avg_pool2d(m, 2 * MASK_FEATHER + 1, stride=1, padding=MASK_FEATHER)
    m = F.interpolate(m, size=(h, w), mode="area").squeeze(1)              # [T, h, w]
    pos = torch.arange(latent_t, dtype=torch.float32) * (float(pixel_frames) / latent_t)
    ramp = ((pos - trim) / float(MASK_RAMP)).clamp(0.0, 1.0)              # context frames stay locked
    m = (m * ramp.view(-1, 1, 1).to(m.device)).clamp(0.0, 1.0)
    coverage = float(masks.mean())
    return m.view(1, 1, latent_t, h, w), coverage


def refine(model, base_positive, sampled, seed, sampler_name, pixel_frames, trim_frames, config, sample,
           sigmas=None, vae=None):
    """Return (latent, report). base_positive: scene conditioning before Motion Context.
    `sample` is the engine's _sample_h3; `sigmas` the scene's main schedule (for "last_step")."""
    trim = int(trim_frames or 0)
    if trim <= 0:
        return sampled, "skipped (no inherited context)"
    video, audio = sampled["samples"].unbind()
    notes = []

    source = sampled
    if config.get("subject"):
        if vae is None:
            raise ValueError("Director 이어받기 보정: 「인물만」에는 Video VAE가 필요합니다.")
        mask, coverage = subject_mask(vae, video, pixel_frames, trim, config["subject_prompt"])
        if mask is None:
            notes.append(f"subject \"{config['subject_prompt']}\" not found, whole frame refined")
        else:
            source = dict(sampled)
            source["noise_mask"] = comfy.nested_tensor.NestedTensor((
                mask.to(video.device, torch.float32), torch.ones_like(audio, dtype=torch.float32)))
            notes.append(f"subject \"{config['subject_prompt']}\" mask {coverage * 100:.0f}% of frame")

    if config.get("mode") == "last_step":
        if sigmas is None or len(sigmas) < 2:
            raise ValueError("Director 이어받기 보정: 「마지막 1스텝」에 쓸 본 생성 스케줄이 없습니다.")
        out = sample(model, base_positive, source, int(seed) + 1, sampler_name, "simple", 1, 1.0,
                     sigmas=sigmas[-2:])
        how = f"last step (sigma {float(sigmas[-2]):.3f})"
    else:
        out = sample(model, base_positive, source, int(seed) + 1, sampler_name, "simple",
                     config["steps"], config["denoise"])
        how = f"{config['steps']} steps, denoise {config['denoise']:.2f}"
    refined = out["samples"].unbind()[0].to(video.device, video.dtype)
    if refined.shape != video.shape:
        raise ValueError("Director refine: video latent layout changed.")
    end = trim + int(config.get("blend_frames") or trim)
    w = blend_weights(video.shape[2], pixel_frames, trim, end, video.device)
    w = w.view(1, 1, -1, 1, 1).to(video.dtype)
    mixed = video * (1 - w) + refined * w
    result = dict(sampled)
    result["samples"] = comfy.nested_tensor.NestedTensor((mixed, audio))
    return result, "; ".join([f"{how}, no context guide, seed+1, original until frame {trim}, "
                              f"refined from frame {end}, audio kept"] + notes)
