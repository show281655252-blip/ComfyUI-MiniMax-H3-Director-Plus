"""Create RefMod files from Director image/video/audio references.

The extraction itself is ComfyUI-MiniMaxH3Mod's ``Create H3 RefMod`` / ``Create H3
Audio RefMod`` nodes, called directly so the saved files stay in that pack's format. Without the pack the route
reports it as unavailable; using existing RefMods never needs it.
"""
import asyncio
import contextlib
import json
import logging
import os
import threading

import torch

import comfy.model_management
import comfy.utils
import folder_paths
import nodes

from .helper_minimax_h3_director import load_audio, load_embedded_video_audio, load_image, load_video
from .helper_refmod_format import refmods_roots

PACK_NODE = "MiniMaxH3RefModExtract"
AUDIO_NODE = "MiniMaxH3RefModAudioExtract"
AUDIO_CONCEPTS = ("voice", "singing", "music_style", "sound_fx", "ambience")
AUDIO_MAX_SECONDS = 30.0
PACK_NAME = "ComfyUI-MiniMaxH3Mod"
PACK_URL = "https://github.com/Luisacaotica/ComfyUI-MiniMaxH3Mod"
MODES = {"full": "Full Reference", "compressed": "Compressed Reference"}
_busy = asyncio.Lock()


def video_vaes():
    return [name for name in folder_paths.get_filename_list("vae") if "minimax_h3_video_vae" in name.lower()]


def audio_vaes():
    return [name for name in folder_paths.get_filename_list("vae") if "minimax_h3_audio_vae" in name.lower()]


def options():
    return {"available": PACK_NODE in nodes.NODE_CLASS_MAPPINGS and AUDIO_NODE in nodes.NODE_CLASS_MAPPINGS,
            "pack": PACK_NAME, "pack_url": PACK_URL, "vaes": video_vaes(), "audio_vaes": audio_vaes(),
            "modes": list(MODES), "audio_concepts": list(AUDIO_CONCEPTS)}


@contextlib.contextmanager
def _no_progress():
    """ComfyUI's progress hook needs a running prompt; this work runs outside the queue.
    Only this thread's progress calls are dropped, a queued prompt keeps its own."""
    original = comfy.utils.PROGRESS_BAR_HOOK
    me = threading.get_ident()

    def hook(*args, **kwargs):
        if threading.get_ident() != me and original is not None:
            return original(*args, **kwargs)

    comfy.utils.set_progress_bar_global_hook(hook)
    try:
        yield
    finally:
        comfy.utils.set_progress_bar_global_hook(original)


class RefModExists(ValueError):
    """A RefMod of that name is already saved."""


def _clean_name(name):
    name = str(name or "").strip()
    if not name or name.startswith(".") or any(ch in name for ch in '/\\:*?"<>|'):
        raise ValueError("RefMod 이름에는 / \\ : * ? \" < > | 를 쓸 수 없고, 비워 둘 수 없습니다.")
    return name


def _trim(payload):
    trim_end = payload.get("trim_end")
    return float(payload.get("trim_start") or 0.0), None if trim_end is None else float(trim_end)


def _create_audio(payload, name):
    extract = nodes.NODE_CLASS_MAPPINGS[AUDIO_NODE]
    concept = payload.get("concept_type") or "voice"
    if concept not in AUDIO_CONCEPTS:
        raise ValueError("알 수 없는 소리 종류입니다.")
    vaes = audio_vaes()
    vae_name = payload.get("audio_vae") or (vaes[0] if vaes else None)
    if vae_name not in vaes:
        raise ValueError("MiniMax H3 Audio VAE(minimax_h3_audio_vae…)를 models/vae에서 찾지 못했습니다.")
    trim_start, trim_end = _trim(payload)
    loader = load_embedded_video_audio if payload.get("source_type") == "video" else load_audio
    audio = loader(payload["value"], folder_paths.get_input_directory(), trim_start=trim_start, trim_end=trim_end)
    if not isinstance(audio, dict) or audio.get("waveform") is None or audio["waveform"].shape[-1] == 0:
        raise ValueError("이 레퍼런스에는 소리가 없습니다.")
    vae = nodes.VAELoader().load_vae(vae_name)[0]
    try:
        with torch.inference_mode(), _no_progress():
            mod = extract().extract(audio=audio, audio_vae=vae, name=name, max_seconds=AUDIO_MAX_SECONDS, max_tokens=5120,
                                    budget_policy="truncate", concept_type=concept,
                                    description=str(payload.get("description") or "").strip(), save=True)[0][0][0]
    finally:
        del vae
        comfy.model_management.soft_empty_cache()
    return {"ok": True, "name": name, "kind": "audio", "tokens": getattr(mod, "token_count", None)}


def create(payload):
    extract = nodes.NODE_CLASS_MAPPINGS.get(PACK_NODE)
    if extract is None or AUDIO_NODE not in nodes.NODE_CLASS_MAPPINGS:
        raise ValueError(f"RefMod를 만들려면 {PACK_NAME} 커스텀 노드가 필요합니다. ({PACK_URL})")
    kind = payload.get("type")
    if kind not in ("image", "video", "audio"):
        raise ValueError("이미지·영상·오디오 레퍼런스만 RefMod로 만들 수 있습니다.")
    name = _clean_name(payload.get("name"))
    for root in refmods_roots():
        if os.path.isfile(os.path.join(root, name + ".safetensors")):
            raise RefModExists(f"'{name}' RefMod가 이미 있습니다. 다른 이름을 쓰세요.")
    if kind == "audio":
        return _create_audio(payload, name)
    mode = MODES.get(payload.get("mode", "full"))
    if mode is None:
        raise ValueError("알 수 없는 RefMod 방식입니다.")
    try:
        pool = int(payload.get("pool") or 16)
        frames = int(payload.get("frames") or 16)
    except (TypeError, ValueError) as exc:
        raise ValueError("압축 격자와 프레임 수는 숫자여야 합니다.") from exc
    if not 2 <= pool <= 64 or not 1 <= frames <= 64:
        raise ValueError("압축 격자는 2~64, 프레임 수는 1~64 범위여야 합니다.")
    vaes = video_vaes()
    vae_name = payload.get("vae") or (vaes[0] if vaes else None)
    if vae_name not in vaes:
        raise ValueError("MiniMax H3 Video VAE(minimax_h3_video_vae…)를 models/vae에서 찾지 못했습니다.")

    input_directory = folder_paths.get_input_directory()
    if kind == "image":
        refs = {"refs_image": {"ref_image_1": load_image(payload["value"], input_directory)}}
    else:
        trim_start, trim_end = _trim(payload)
        refs = {"refs_video": {"ref_video_1": load_video(
            payload["value"], input_directory, trim_start=trim_start, trim_end=trim_end)}}

    vae = nodes.VAELoader().load_vae(vae_name)[0]
    try:
        with torch.inference_mode(), _no_progress():  # nodes run under inference mode in a normal queue
            # max_tokens=0: no budget, the chosen grid and frame count decide the size
            output = extract.execute(name=name, mode=mode, vae=vae, max_tokens=0,
                                     pool_h=pool, pool_w=pool, latent_frames=frames,
                                     description=str(payload.get("description") or "").strip(), save=True, **refs)
    finally:
        del vae
        comfy.model_management.soft_empty_cache()
    details = json.loads(output.result[1])
    return {"ok": True, "name": name, "kind": details.get("kind", kind), "tokens": details.get("tokens")}


def register_routes(server):
    from aiohttp import web

    @server.routes.get("/director_plus/refmod/create")
    async def create_options(_request):
        return web.json_response(options())

    @server.routes.post("/director_plus/refmod/create")
    async def create_route(request):
        if _busy.locked():
            return web.json_response({"ok": False, "error": "다른 RefMod를 만드는 중입니다."}, status=409)
        if server.prompt_queue.get_tasks_remaining() > 0:
            return web.json_response({"ok": False, "error": "영상 생성이 끝난 뒤 다시 시도하세요. (생성 중에는 VRAM이 부족합니다)"}, status=409)
        async with _busy:
            try:
                payload = await request.json()
                return web.json_response(await asyncio.to_thread(create, payload))
            except ValueError as exc:
                return web.json_response({"ok": False, "error": str(exc), "exists": isinstance(exc, RefModExists)}, status=400)
            except Exception as exc:  # the extractor is another pack's code: report, never a bare 500
                logging.exception("[Director Plus] RefMod creation failed")
                return web.json_response({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=500)
