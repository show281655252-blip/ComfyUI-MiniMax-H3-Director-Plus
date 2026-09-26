# Modified for Director Plus isolation, 2026-09-26. See NOTICE.md for upstream attribution.
"""Director scene controls backed by the Extender's existing disk cache."""

import copy

import hashlib

from ..director import nodes_enhanced_video_combine as combine_module
from ..director.nodes_enhanced_video_combine import DaSiWa_EnhancedVideoCombine

import json

import subprocess

from pathlib import Path

import av

import numpy as np

import torch

import folder_paths

import nodes

import comfy.nested_tensor

import comfy.samplers

from server import PromptServer

from comfy_extras.nodes_minimax_h3 import _encode_ref_audio

from .extender import MiniMaxH3Extender, _manual_effective_resolution

from .motion_context_disk import MiniMaxH3MotionContextDiskFinalDecode, _find_ffmpeg, _comfy_media_item, _video_output_from_path

def source_path(filename):

    root = Path(folder_paths.get_input_directory()).resolve()

    path = (root / filename).resolve()

    if not path.is_relative_to(root) or not path.is_file():

        raise ValueError("Director: select an existing video from the input folder.")

    return path

def video_info(path):

    with av.open(str(path)) as container:

        stream = container.streams.video[0]

        duration = float(stream.duration * stream.time_base) if stream.duration else float(container.duration or 0) / av.time_base

        return duration, bool(container.streams.audio)

def read_source_tail(path, width, height, count):

    duration, has_audio = video_info(path)

    ffmpeg = _find_ffmpeg()

    scale = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"

    command = [ffmpeg, "-v", "error", "-ss", str(max(0, duration - count / 24 - 1)), "-i", str(path),

               "-an", "-vf", f"fps=24,{scale}", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]

    result = subprocess.run(command, check=True, capture_output=True)

    frames = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, height, width, 3)

    if not len(frames):

        raise ValueError("Director: the source video contains no decodable frames.")

    frames = frames[-count:]

    if len(frames) < count:

        frames = np.concatenate([np.repeat(frames[:1], count - len(frames), axis=0), frames])

    images = torch.from_numpy(frames.copy()).float().div_(255)

    sample_count = round(count / 24 * 32000)

    audio = np.zeros((sample_count, 2), dtype=np.float32)

    if has_audio:

        result = subprocess.run([ffmpeg, "-v", "error", "-ss", str(max(0, duration - count / 24)),

                                 "-i", str(path), "-vn", "-t", str(count / 24), "-ar", "32000", "-ac", "2",

                                 "-f", "f32le", "pipe:1"], check=True, capture_output=True)

        samples = np.frombuffer(result.stdout, dtype=np.float32).reshape(-1, 2)

        length = min(len(samples), sample_count)

        if length:

            audio[-length:] = samples[-length:]

    return images, {"waveform": torch.from_numpy(audio.copy()).T.unsqueeze(0), "sample_rate": 32000}

def encode_source_tail(path, width, height, count, vae, audio_vae):

    images, audio = read_source_tail(path, width, height, count)

    video_latent = vae.encode(images)

    audio_latent, _ = _encode_ref_audio(audio_vae, audio)

    return {"samples": comfy.nested_tensor.NestedTensor((video_latent, audio_latent))}

def prepare_state(guide):

    state = copy.deepcopy(guide["long_video"])
    if state.get("source_mode_enabled") is False:
        state["start_mode"] = "new"
        state.pop("source_video", None)

    path = source_path(state["source_video"]) if state.get("start_mode") == "video" else None

    source_key = (str(path), path.stat().st_size, path.stat().st_mtime_ns) if path else None

    signature = json.dumps([source_key, guide["width"], guide["height"], state.get("context_length", "22")])

    owner = "director_" + state["project_id"] + "_" + hashlib.sha256(signature.encode()).hexdigest()[:12]

    clips = state.get("clips", [])

    if not clips:

        raise ValueError("Director: add at least one scene.")

    if state.get("cache_owner") != owner:

        for clip in clips:

            clip["validated"] = False

    active_seen = False

    for clip in clips:

        clip.setdefault("use_external_prompt", not bool(str(clip.get("prompt", "")).strip()))

        if clip.get("validated", False):

            continue

        active = state.get("run_mode", "clip_by_clip") == "full_batch" or not active_seen

        if active and clip["use_external_prompt"]:

            clip["prompt"] = guide["resolved_prompt"]

        active_seen = True

    state["cache_owner"] = owner

    return state, path

class DirectorPlusGenerate:

    @classmethod

    def INPUT_TYPES(cls):

        return {"required": {

            "guide": ("MINIMAX_H3_DIRECTOR_GUIDE",), "model": ("MODEL",), "clip": ("CLIP",),

            "vae": ("VAE",), "audio_vae": ("VAE",), "sigmas": ("SIGMAS",),

            "sampler_name": (comfy.samplers.SAMPLER_NAMES,),

        }}

    RETURN_TYPES = ("H3_MOTION_DISK_CACHE",)

    FUNCTION = "generate"

    CATEGORY = "MiniMax H3"

    @classmethod

    def IS_CHANGED(cls, **kwargs):

        return float("nan")

    def generate(self, guide, model, clip, vae, audio_vae, sigmas, sampler_name):

        if guide.get("minimax_ref_items"):

            raise ValueError("Director long video: use image/video/audio references instead of RefMod files, or turn long video off.")

        guide = dict(guide)

        guide["width"], guide["height"] = _manual_effective_resolution(guide["width"], guide["height"])

        state, path = prepare_state(guide)

        owner = state["cache_owner"]

        initial_context = None

        if path and not state["clips"][0].get("validated", False):

            initial_context = encode_source_tail(path, guide["width"], guide["height"], int(state.get("context_length", "22")), vae, audio_vae)

        refs = guide.get("ref_images", {})

        pack = {"type": "H3_REF_PACK", "version": 1, "source": "MiniMax H3 Director", "count": len(refs),

                "slots": [refs.get(f"ref_image_{i}") for i in range(1, 10)]}

        media = {}

        for i in range(1, 4):

            media[f"ref_video_{i}"] = guide.get("ref_videos", {}).get(f"ref_video_{i}")

            media[f"ref_video_fps_{i}"] = 24.0

            media[f"ref_video_audio_{i}"] = guide.get("ref_video_audios", {}).get(f"ref_video_audio_{i}")

            media[f"ref_audio_{i}"] = guide.get("ref_audios", {}).get(f"ref_audio_{i}")

        result = MiniMaxH3Extender().extend(

            model=model, clip=clip, vae=vae, audio_vae=audio_vae,

            run_mode=state.get("run_mode", "clip_by_clip"), width=guide["width"], height=guide["height"],

            ref_image_size=guide["ref_image_size"], steps=len(sigmas) - 1, sampler_name=sampler_name,

            scheduler="simple", denoise=1.0, context_length=str(state.get("context_length", "22")),

            audio_context_length=0, clips_json=json.dumps({"version": 2, "clips": state["clips"]}),

            resolution_mode="manual", refs_json=json.dumps({"version": 2, "refs": [None] * 9}),

            generation_mode="ref2va", motion_context=True, ref_pack=pack,

            unique_id=owner, sigmas=sigmas, initial_context=initial_context, **media,

        )

        prepared_scenes = {c["id"]: c for c in state["clips"]}

        ui = result["ui"]["h3_extender_state"][0]

        state["clips"] = json.loads(ui["clips_json"])["clips"]

        for scene in state["clips"]:

            prepared = prepared_scenes[scene["id"]]

            scene["prompt"] = prepared["prompt"]

            scene["use_external_prompt"] = prepared["use_external_prompt"]

        cache = dict(result["result"][0])

        cache["director_source"] = str(path) if path else ""

        cache["director_source_context"] = int(state.get("context_length", "22"))

        cache["director_width"] = guide["width"]

        cache["director_height"] = guide["height"]

        cache["director_project_id"] = state["project_id"]

        PromptServer.instance.send_sync("director-plus-long-state", {"project_id": state["project_id"], "state": state, "ui": ui})

        return (cache,)

def source_color_filter(source, continuation, duration, context_frames, strength):

    if strength == 0:

        return ""

    samples = []

    for path, start in ((source, max(0, duration - 4 / 24)), (continuation, context_frames / 24)):

        result = subprocess.run([

            _find_ffmpeg(), "-v", "error", "-ss", str(start), "-i", str(path),

            "-an", "-vf", "fps=24,scale=160:160:force_original_aspect_ratio=increase,crop=160:160",

            "-frames:v", "4", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1",

        ], check=True, capture_output=True)

        pixels = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, 3).astype(np.float32)

        if not len(pixels):

            raise ValueError("Director: no boundary frames available for source color matching.")

        samples.append((pixels.mean(axis=0), pixels.std(axis=0)))

    (ref_mean, ref_std), (src_mean, src_std) = samples

    gain = np.clip(ref_std / np.maximum(src_std, 1.0), 0.5, 2.0)

    offset = (ref_mean - src_mean * gain) * strength

    gain = 1 + (gain - 1) * strength

    return "lutrgb=" + ":".join(

        f"{channel}='clip(val*{float(g):.8f}+({float(o):.8f}),0,255)'"

        for channel, g, o in zip("rgb", gain, offset)

    )

def concatenate_source(source, continuation, width, height, prefix, context_frames, output_directory=None, crf=18, color_match_strength=0.5):

    source = source_path(str(Path(source).relative_to(Path(folder_paths.get_input_directory()).resolve())))

    duration, has_audio = video_info(source)

    out_dir, name, counter, subfolder, _ = folder_paths.get_save_image_path(prefix, output_directory or folder_paths.get_output_directory(), width, height)

    output = Path(out_dir) / f"{name}_{counter:05}_continued.mp4"

    scale = f"fps=24,scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,setpts=PTS-STARTPTS"

    command = [_find_ffmpeg(), "-v", "error", "-i", str(source), "-ss", str(context_frames / 24), "-i", str(continuation)]

    color_filter = source_color_filter(source, continuation, duration, context_frames, color_match_strength)

    correction = f"format=rgb24,{color_filter}," if color_filter else ""

    filters = f"[0:v]{scale}[v0];[1:v]fps=24,setsar=1,{correction}format=yuv420p,setpts=PTS-STARTPTS[v1];"

    if has_audio:

        filters += f"[0:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={duration},asetpts=PTS-STARTPTS[a0];"

    else:

        filters += f"anullsrc=r=48000:cl=stereo,atrim=duration={duration},asetpts=PTS-STARTPTS[a0];"

    filters += "[1:a]aresample=48000,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"

    command += ["-filter_complex", filters, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "fast", "-crf", str(crf),

                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-n", str(output)]

    subprocess.run(command, check=True, capture_output=True)

    return output

class DirectorPlusVideoOutput:

    @classmethod

    def INPUT_TYPES(cls):

        schema = copy.deepcopy(DaSiWa_EnhancedVideoCombine.INPUT_TYPES())

        for name in ("images", "frame_rate"):

            typ, options = schema["required"][name]

            schema["required"][name] = (typ, {**options, "lazy": True})

        typ, options = schema["optional"]["audio"]

        schema["optional"]["audio"] = (typ, {**options, "lazy": True})

        schema["required"]["director_guide"] = ("MINIMAX_H3_DIRECTOR_GUIDE",)

        schema["optional"].update({"long_cache": ("H3_MOTION_DISK_CACHE", {"lazy": True}),

                                   "video_vae": ("VAE", {"lazy": True}), "audio_vae": ("VAE", {"lazy": True})})

        return schema

    RETURN_TYPES = ("IMAGE", "STRING")

    RETURN_NAMES = ("frames", "filename")

    FUNCTION = "save"

    CATEGORY = "MiniMax H3"

    OUTPUT_NODE = True

    @classmethod

    def IS_CHANGED(cls, **kwargs):

        return float("nan")

    def check_lazy_status(self, director_guide, images=None, frame_rate=None, audio=None, long_cache=None, video_vae=None, audio_vae=None, **kwargs):

        if director_guide.get("long_video", {}).get("enabled"):

            return [k for k, v in (("long_cache", long_cache), ("video_vae", video_vae), ("audio_vae", audio_vae)) if v is None]

        return [k for k, v in (("images", images), ("frame_rate", frame_rate), ("audio", audio)) if v is None]

    def save(self, director_guide, images=None, frame_rate=None, audio=None, long_cache=None, video_vae=None, audio_vae=None, **kwargs):

        if not director_guide.get("long_video", {}).get("enabled"):

            return DaSiWa_EnhancedVideoCombine().combine(images=images, frame_rate=frame_rate, audio=audio, **kwargs)

        media_type = "output" if kwargs.get("save_output", True) else "temp"

        output_directory = folder_paths.get_output_directory() if media_type == "output" else folder_paths.get_temp_directory()


        prefix = combine_module._format_filename_prefix(kwargs.get("filename_prefix", "video_%date:hhmmss%"), seed=kwargs.get("seed"))

        output_directory, filename, counter, _, _ = folder_paths.get_save_image_path(

            prefix, output_directory, long_cache["director_width"], long_cache["director_height"]

        )

        prefix = f"{filename}_{counter:05}"

        quality = int(kwargs.get("quality", 18))

        result = MiniMaxH3MotionContextDiskFinalDecode().export(

            cache=long_cache, vae=video_vae, audio_vae=audio_vae, fps=24.0,

            filename_prefix=prefix, output_directory=output_directory, codec="H.264", crf=quality,

            preset="fast", audio_bitrate="192k", autoplay=False,

            prompt=kwargs.get("prompt"), extra_pnginfo=kwargs.get("extra_pnginfo"),

        )

        video = result["result"][0]

        path = Path(video.get_stream_source())

        if long_cache.get("director_source"):

            path = concatenate_source(long_cache["director_source"], path, long_cache["director_width"], long_cache["director_height"], filename, long_cache["director_source_context"], output_directory, quality, float(director_guide["long_video"].get("source_color_strength", 0.5)))

        item = _comfy_media_item(path, 24.0, media_type)

        item.update(codec="H.264", container="MP4", bit_depth=8, fps=24.0, width=long_cache["director_width"], height=long_cache["director_height"])

        scenes = []
        if not long_cache.get("director_source"):
            clip_ids = [c["id"] for c in director_guide["long_video"]["clips"]]
            for span in result["ui"]["h3_preview_info"][0]["color_timeline"]:
                if span["index"] < len(clip_ids):
                    scenes.append({"id": clip_ids[span["index"]], "start": span["start"], "end": span["end"]})
        PromptServer.instance.send_sync("director-plus-long-preview", {"project_id": long_cache["director_project_id"], "video": item, "scenes": scenes, "path": str(path)})

        frames = _video_output_from_path(path).get_components().images if kwargs.get("pass_frames") else torch.empty((0, long_cache["director_height"], long_cache["director_width"], 3))

        return {"ui": {"videos": [item]}, "result": (frames, str(path))}

NODE_CLASS_MAPPINGS = {"DirectorPlusGenerate": DirectorPlusGenerate, "DirectorPlusVideoOutput": DirectorPlusVideoOutput}

NODE_DISPLAY_NAME_MAPPINGS = {"DirectorPlusGenerate": "Director · Ref2VA Motion Context", "DirectorPlusVideoOutput": "Director · Video Output"}

