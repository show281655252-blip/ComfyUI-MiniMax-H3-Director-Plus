"""Face refine for each long-video scene, using ComfyUI-H3-FaceRefine's own nodes.

H3 draws a face badly when it is a small part of the frame. H3-FaceRefine
(https://github.com/Carasibana/ComfyUI-H3-FaceRefine, MIT) tracks the face through the clip, crops
it so it fills a canvas, lets H3 redraw the crops video-to-video at a low denoise, and pastes the
face back with colour matching. The nodes are called from the installed pack, the way LBH calls the
latent upscaler and Motion Lab calls MAINodes; nothing of the pack is copied here.

Director specifics:
- runs on the finished scene (after Motion Lab, LBH and audio regen), before the scene is cached, so
  the next scene's Motion Context and the final join see the refined face;
- the crop pass is conditioned on the scene's own prompt and reference images (re-encoded for the
  crop canvas, aspect kept); keyframes are left out because they describe the whole frame;
- the scene's audio is held (noise mask zero) while the crops are redrawn, so the mouth follows the
  scene's real audio — what the pack's examples use MiniMaxH3NativeAudioLock for — and the scene
  keeps its audio unchanged;
- the redraw uses the scene's own model and step count with the pack example's denoise 0.4 and
  er_sde; the canvas is the pack's auto mode (at least 512, at most 768);
- a scene with no detectable face is left as generated.
"""
import logging
import math

import comfy.nested_tensor
import nodes
import torch

from . import director_lbh

NODES = ("H3FaceTrackCrop", "H3InjectVideoLatent", "H3PerFrameDenoise", "H3FaceStitch")
DENOISE = 0.4
SAMPLER = "er_sde"
DETECTOR = "face_yolov8m.pt"
FALLBACK = "person_yolov8m-seg.pt"


def settings(enabled=False):
    if not enabled:
        return None
    return {"version": 1, "denoise": DENOISE, "sampler": SAMPLER, "canvas": "auto_capped_768",
            "crop_factor": 3.0, "detector": DETECTOR}


def check_installed():
    missing = [name for name in NODES if name not in nodes.NODE_CLASS_MAPPINGS]
    if missing:
        raise ValueError(
            "Director 얼굴 다듬기: ComfyUI-H3-FaceRefine 노드가 없습니다 (" + ", ".join(missing) + "). "
            "https://github.com/Carasibana/ComfyUI-H3-FaceRefine 를 설치하거나 Settings에서 얼굴 다듬기를 끄세요.")


def _node(name):
    return nodes.NODE_CLASS_MAPPINGS[name]()


def _option(choices, name):
    """The tracker lists detector files with or without their bbox\\ / segm\\ folder; take either."""
    for choice in choices:
        if choice.replace("\\", "/").split("/")[-1] == name:
            return choice
    return None


def _frames(vae, video):
    frames = vae.decode(video)
    if frames.ndim == 5 and frames.shape[0] == 1:
        frames = frames[0]
    return frames[..., :3]


def crop_conditioning(conditioning, base_width, base_height, canvas_w, canvas_h, vae):
    """The scene's conditioning for the crop canvas: references scaled by area (aspect kept), as
    MiniMaxH3ReferenceToVideo's "match" does, and no keyframes (they show the whole frame)."""
    scale = math.sqrt((canvas_w * canvas_h) / float(base_width * base_height))
    result = []
    for embedding, metadata in conditioning:
        metadata = dict(metadata)
        metadata.pop("minimax_keyframes", None)
        if "minimax_refs" in metadata:
            blocks = []
            for block in metadata["minimax_refs"]:
                block = dict(block)
                z = block.get("latent")
                if z is not None and block.get("kind") != "audio":
                    tw = max(2, round(z.shape[-1] * scale / 2) * 2)
                    th = max(2, round(z.shape[-2] * scale / 2) * 2)
                    block["latent"] = director_lbh.reencode_visual(
                        z, tw, th, vae, block.get("_director_source_pixels"), "disabled")
                    block.pop("_director_source_pixels", None)
                    if "latent_h" in block:
                        block.update(latent_h=th, latent_w=tw)
                blocks.append(block)
            metadata["minimax_refs"] = blocks
        result.append([embedding, metadata])
    return result


def refine(model, positive, base_width, base_height, sampled, steps, seed, vae, config, sample_fn):
    """Return (latent, report). The latent keeps sampled's audio; the face in its video is redrawn."""
    video, audio = sampled["samples"].unbind()
    frames = _frames(vae, video)

    tracker = _node("H3FaceTrackCrop")
    choices = type(tracker).INPUT_TYPES()["required"]["detector"][0]
    fallbacks = type(tracker).INPUT_TYPES()["optional"]["fallback_detector"][0]
    detector = _option(choices, config["detector"])
    if detector is None:
        raise ValueError(f"Director 얼굴 다듬기: 얼굴 감지 모델 {config['detector']}이 models/ultralytics/bbox에 없습니다.")
    try:
        crops, transform, _preview, track_report, canvas_w, canvas_h, _count = tracker.run(
            frames, detector, 0.35, float(config["crop_factor"]), 768, 768, config["canvas"],
            21, 51, "gaussian", "per_frame", select="largest_face",
            fallback_detector=_option(fallbacks, FALLBACK) or "none")
    except ValueError as error:
        if "No face detected" not in str(error):
            raise
        return sampled, "no face detected; scene kept as generated"

    cond = crop_conditioning(positive, base_width, base_height, canvas_w, canvas_h, vae)
    # The crops go into the video stream; the scene's own audio stays in the audio stream and is held
    # by the per-frame denoise mask (its audio side is zero), so the redraw lip-syncs to it.
    template = torch.zeros(tuple(video.shape[:-2]) + (int(canvas_h) // 16, int(canvas_w) // 16),
                           dtype=video.dtype, device=video.device)
    av = {"samples": comfy.nested_tensor.NestedTensor((template, audio))}
    av = _node("H3InjectVideoLatent").run(av, crops, vae)[0]
    del crops
    av, denoise_report, patched = _node("H3PerFrameDenoise").run(
        model, av, transform, 1.0, 0.35, 30.0, 120.0, 1.0, 9, scale_mode="absolute_px")
    redrawn = sample_fn(patched, cond, av, seed, config["sampler"], "simple", int(steps), float(config["denoise"]))
    del av, patched
    refined_crops = _frames(vae, redrawn["samples"].unbind()[0])
    del redrawn
    stitched = _node("H3FaceStitch").run(frames, refined_crops, transform, "face_only", 24, 24, 1.0, 1.0,
                                         undetected_frames="fade_out")[0]
    del frames, refined_crops
    new_video = vae.encode(stitched).to(device=video.device, dtype=video.dtype)
    if new_video.shape != video.shape:
        raise RuntimeError(f"Director 얼굴 다듬기: re-encoded video {tuple(new_video.shape)} != scene {tuple(video.shape)}.")
    out = dict(sampled)
    out["samples"] = comfy.nested_tensor.NestedTensor((new_video, audio))
    lines = [line for line in track_report.splitlines() if line.startswith(("frames=", "face height", "magnification"))]
    strength = next((line.strip() for line in denoise_report.splitlines() if "MULTIPLIER" in line), "")
    report = f"canvas {canvas_w}x{canvas_h}, {int(steps)} steps x denoise {config['denoise']}; " + " | ".join(lines + [strength])
    logging.info("[Director Plus] face refine: %s", report)
    return out, report
