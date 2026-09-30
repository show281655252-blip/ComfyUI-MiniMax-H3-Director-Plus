"""Create RefMod files from Director image/video references.

The extraction itself is ComfyUI-MiniMaxH3Mod's ``Create H3 RefMod`` node, called
directly so the saved files stay in that pack's format. Without the pack the route
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

from .helper_minimax_h3_director import load_image, load_video
from .helper_refmod_format import refmods_roots

PACK_NODE = "MiniMaxH3RefModExtract"
PACK_NAME = "ComfyUI-MiniMaxH3Mod"
PACK_URL = "https://github.com/Luisacaotica/ComfyUI-MiniMaxH3Mod"
MODES = {"full": "Full Reference", "compressed": "Compressed Reference"}
_busy = asyncio.Lock()


def video_vaes():
    return [name for name in folder_paths.get_filename_list("vae") if "minimax_h3_video_vae" in name.lower()]


def options():
    return {"available": PACK_NODE in nodes.NODE_CLASS_MAPPINGS, "pack": PACK_NAME, "pack_url": PACK_URL,
            "vaes": video_vaes(), "modes": list(MODES)}


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


def _clean_name(name):
    name = str(name or "").strip()
    if not name or name.startswith(".") or any(ch in name for ch in '/\\:*?"<>|'):
        raise ValueError("RefMod 이름에는 / \\ : * ? \" < > | 를 쓸 수 없고, 비워 둘 수 없습니다.")
    return name


def create(payload):
    extract = nodes.NODE_CLASS_MAPPINGS.get(PACK_NODE)
    if extract is None:
        raise ValueError(f"RefMod를 만들려면 {PACK_NAME} 커스텀 노드가 필요합니다. ({PACK_URL})")
    kind = payload.get("type")
    if kind not in ("image", "video"):
        raise ValueError("이미지나 영상 레퍼런스만 RefMod로 만들 수 있습니다.")
    mode = MODES.get(payload.get("mode", "full"))
    if mode is None:
        raise ValueError("알 수 없는 RefMod 방식입니다.")
    name = _clean_name(payload.get("name"))
    for root in refmods_roots():
        if os.path.isfile(os.path.join(root, name + ".safetensors")):
            raise ValueError(f"'{name}' RefMod가 이미 있습니다. 다른 이름을 쓰세요.")
    vaes = video_vaes()
    vae_name = payload.get("vae") or (vaes[0] if vaes else None)
    if vae_name not in vaes:
        raise ValueError("MiniMax H3 Video VAE(minimax_h3_video_vae…)를 models/vae에서 찾지 못했습니다.")

    input_directory = folder_paths.get_input_directory()
    if kind == "image":
        refs = {"refs_image": {"ref_image_1": load_image(payload["value"], input_directory)}}
    else:
        trim_end = payload.get("trim_end")
        refs = {"refs_video": {"ref_video_1": load_video(
            payload["value"], input_directory, trim_start=float(payload.get("trim_start") or 0.0),
            trim_end=None if trim_end is None else float(trim_end))}}

    vae = nodes.VAELoader().load_vae(vae_name)[0]
    try:
        with torch.inference_mode(), _no_progress():  # nodes run under inference mode in a normal queue
            output = extract.execute(name=name, mode=mode, vae=vae, max_tokens=5120,
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
                return web.json_response({"ok": False, "error": str(exc)}, status=400)
            except Exception as exc:  # the extractor is another pack's code: report, never a bare 500
                logging.exception("[Director Plus] RefMod creation failed")
                return web.json_response({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=500)
