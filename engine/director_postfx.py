"""Motion Lab (de-rope) and face refine as plain nodes for the single-video path.

The long-video engine runs these two steps per scene (engine/director_derope.py and
engine/director_face_refine.py). The single-video graph (FL2VA / Ref2VA samplers inside the Settings
subgraph) has no scene loop, so the same functions are exposed as nodes that take the finished
latent, the model and the conditioning the final sampler used, and return the corrected latent:

    final latent -> Motion Lab -> face refine -> video decode / audio regen

Both nodes pass the latent through untouched while `enabled` is off, and both keep the latent's
audio unchanged. With LBH on, they work on the final (high resolution) latent, so they cost more
than in the long-video engine, which runs Motion Lab before the upscale.
"""
import comfy.samplers

from . import director_derope, director_face_refine


def _sample_h3():
    from .extender import _sample_h3  # lazy: the engine module is heavy and already loaded by DirectorPlusGenerate
    return _sample_h3


def _video_size(latent):
    samples = latent["samples"]
    if getattr(samples, "is_nested", False):
        samples = samples.unbind()[0]
    if samples.ndim != 5:
        raise ValueError("Director Plus: expected a video latent.")
    return int(samples.shape[-1]) * 16, int(samples.shape[-2]) * 16


class DirectorPlusMotionLab:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "conditioning": ("CONDITIONING",),
            "latent": ("LATENT",),
            "sigmas": ("SIGMAS",),
            "vae": ("VAE",),
            "frame_count": ("INT", {"default": 121, "min": 1, "max": 4096, "tooltip": "Pixel frames of the video (the Director's frame count)."}),
            "noise_seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
            "enabled": ("BOOLEAN", {"default": False}),
        }}

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "execute"
    CATEGORY = "Director Plus/postfx"

    def execute(self, model, conditioning, latent, sigmas, vae, frame_count, noise_seed, sampler_name, enabled):
        if not enabled:
            return (latent,)
        director_derope.check_installed()
        out, report = director_derope.derope(
            model, conditioning, latent, sigmas, int(noise_seed), str(sampler_name), vae, int(frame_count), 0,
            director_derope.settings(True), _sample_h3())
        print(f"Director Plus Motion Lab (single video): {report}")
        return (out,)


class DirectorPlusFaceRefine:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "conditioning": ("CONDITIONING",),
            "latent": ("LATENT",),
            "vae": ("VAE",),
            "steps": ("INT", {"default": 8, "min": 1, "max": 200, "tooltip": "Total steps of the generation schedule (the redraw uses this many steps at a low denoise)."}),
            "noise_seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            "enabled": ("BOOLEAN", {"default": False}),
        }}

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "execute"
    CATEGORY = "Director Plus/postfx"

    def execute(self, model, conditioning, latent, vae, steps, noise_seed, enabled):
        if not enabled:
            return (latent,)
        director_face_refine.check_installed()
        width, height = _video_size(latent)
        out, report = director_face_refine.refine(
            model, conditioning, width, height, latent, int(steps), int(noise_seed), vae,
            director_face_refine.settings(True), _sample_h3())
        print(f"Director Plus face refine (single video): {report}")
        return (out,)
