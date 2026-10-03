"""Motion Lab de-rope for each long-video scene, using ComfyUI-MAINodes' own nodes.

H3 smears bursty motion because one latent token spans four pixel frames. MAINodes' fix
(https://github.com/matlowai/ComfyUI-MAINodes, GPL-3.0): read where the motion runs too hot from
the scene's latent (H3 Jerk Oracle), hold those frames so the clip gets longer (H3 Time Smear),
regenerate it video-to-video on the tail of the schedule (H3 V2V Init + partial sigmas), then drop
the held frames again (H3 Exact Recover). The nodes are called from the installed pack, the way LBH
calls the latent upscaler; nothing of the pack is copied here.

Director specifics:
- runs on the scene's first-pass latent at base resolution, before LBH and audio regen;
- the Motion Context prefix (the previous scene's frames this scene starts with) is never held, so
  the scene still begins exactly where the previous one ended;
- the scene keeps its first-pass audio (the pack's "keep the original performance" default);
- the recovered frames are VAE-encoded back to a latent, because the scene cache, the next scene's
  context and the final join all work on latents.
"""
import json
import logging

import comfy.nested_tensor
import nodes

NODES = ("H3JerkOracle", "H3TimeSmear", "H3V2VInit", "H3ExactRecover")
ORACLE_PRESET = "balanced (default)"   # q 0.75, d_max 4, ramp on
INJECT = 0.70                          # H3 Inject Schedule's default: share of the schedule that re-runs


def settings(enabled=False):
    if not enabled:
        return None
    return {"version": 1, "oracle": ORACLE_PRESET, "inject": INJECT, "bridge": 8}


def check_installed():
    missing = [name for name in NODES if name not in nodes.NODE_CLASS_MAPPINGS]
    if missing:
        raise ValueError(
            "Director Motion Lab (de-rope): ComfyUI-MAINodes 노드가 없습니다 (" + ", ".join(missing) + "). "
            "https://github.com/matlowai/ComfyUI-MAINodes 를 설치하거나 Settings에서 Motion Lab을 끄세요.")


def _node(name):
    return nodes.NODE_CLASS_MAPPINGS[name]()


def _frames(vae, video):
    frames = vae.decode(video)
    if frames.ndim == 5 and frames.shape[0] == 1:
        frames = frames[0]
    return frames[..., :3]


def derope(model, positive, sampled, sigmas, seed, sampler_name, vae, frame_count, protect_frames,
           config, sample_fn):
    """Return (latent, report). The latent keeps sampled's audio; its video is de-roped."""
    video, audio = sampled["samples"].unbind()
    oracle = _node("H3JerkOracle").read(
        {"samples": sampled["samples"]}, int(frame_count), 0.75, 4, True,
        preset=config["oracle"], bridge=int(config["bridge"]))
    hold_map = json.loads(oracle[0])
    holds = list(hold_map["holds"])
    keep = min(int(protect_frames or 0), len(holds))
    holds[:keep] = [1] * keep                       # never stretch the carried Motion Context
    if max(holds) <= 1:
        return sampled, "no fast-motion span found; scene kept as generated"
    hold_map["holds"] = holds

    frames = _frames(vae, video)
    if frames.shape[0] != len(holds):
        raise RuntimeError(f"Director de-rope: decoded {frames.shape[0]} frames, hold map covers {len(holds)}.")
    smeared, hold_used, smear_len, _ = _node("H3TimeSmear").smear(frames, 4, hold_map=json.dumps(hold_map))
    del frames
    init = _node("H3V2VInit").build({"samples": vae.encode(smeared)})[0]
    del smeared

    steps = len(sigmas) - 1
    run = max(1, int(round(steps * float(config["inject"]))))
    regenerated = sample_fn(model, positive, init, seed, sampler_name, "simple", run, 1.0,
                            sigmas=sigmas[-(run + 1):])
    del init
    regen_video = regenerated["samples"].unbind()[0]
    recovered = _node("H3ExactRecover").recover(_frames(vae, regen_video), hold_used)[0]
    del regenerated, regen_video
    new_video = vae.encode(recovered).to(device=video.device, dtype=video.dtype)
    if new_video.shape != video.shape:
        raise RuntimeError(f"Director de-rope: re-encoded video {tuple(new_video.shape)} != scene {tuple(video.shape)}.")
    out = dict(sampled)
    out["samples"] = comfy.nested_tensor.NestedTensor((new_video, audio))
    held = sum(1 for h in holds if h > 1)
    report = (f"{held}/{len(holds)} frames held (max x{max(holds)}, first {keep} context frames kept), "
              f"regenerated as {smear_len} frames with the last {run} of {steps} steps")
    logging.info("[Director Plus] Motion Lab de-rope: %s", report)
    return out, report
