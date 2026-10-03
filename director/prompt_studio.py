"""Prompt Studio: write the Director's prompt with ComfyUI-MinimaxH3-PromptDirector.

The window on the Director node replaces the Writer / Freeze / Shot Builder node chain: this
module calls those nodes' implementations directly (the pattern of MMH3 Studio's pack_bridge,
MIT, Bokuwako), outside the ComfyUI queue. The Director Plus timeline is handed to the writer
as-is, so the video-reference analysis and V+A sound rules of prompt_director_video apply.

Without PromptDirector installed the catalog reports it as unavailable.
"""
import asyncio
import inspect
import json
import logging
import time
from urllib import request as urlrequest

import comfy.model_management
import nodes

WRITER = "MMH3_OllamaPromptWriter"
BUILDER = "MMH3_ShotBuilder"
SETTINGS = "MMH3_ShotSettings"
FREEZE = "MMH3_PromptFreeze"
PACK_URL = "https://github.com/Bokuwako/ComfyUI-MinimaxH3-PromptDirector"
SETTING_KEYS = ("style", "theme", "lens", "depth_of_field", "lighting_key", "dialogue_mode",
                "dialogue_language", "include_soundscape", "include_music", "must_not",
                "must_happen", "custom_style", "progression", "progression_target", "progression_seed")
WRITER_KEYS = ("model", "vision_model", "temperature", "llm_seed", "num_ctx", "max_tokens",
               "max_words", "vision_pass", "image_max_side", "max_ref_images", "auto_fix",
               "force_english", "ollama_url")
_busy = asyncio.Lock()


def _cls(name):
    return nodes.NODE_CLASS_MAPPINGS.get(name)


def available():
    return all(_cls(name) for name in (WRITER, BUILDER, SETTINGS, FREEZE))


def _defaults(cls):
    out = {}
    for group in ("required", "optional"):
        for key, spec in cls.INPUT_TYPES().get(group, {}).items():
            config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if "default" in config:
                out[key] = config["default"]
            elif isinstance(spec[0], (list, tuple)) and spec[0]:
                out[key] = spec[0][0]
    return out


def _schema(cls, keys):
    """{key: {kind, options, default}} for the widgets the window shows."""
    out = {}
    types = cls.INPUT_TYPES()
    for group in ("required", "optional"):
        for key, spec in types.get(group, {}).items():
            if key not in keys:
                continue
            config = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            kind = spec[0]
            if isinstance(kind, (list, tuple)):
                out[key] = {"kind": "combo", "options": list(kind), "default": config.get("default", kind[0] if kind else "")}
            else:
                out[key] = {"kind": str(kind).lower(), "default": config.get("default"),
                            "min": config.get("min"), "max": config.get("max"), "step": config.get("step"),
                            "tooltip": config.get("tooltip", "")}
            if config.get("tooltip"):
                out[key]["tooltip"] = config["tooltip"]
    return out


def _ollama_models(base):
    try:
        with urlrequest.urlopen(base.rstrip("/") + "/api/tags", timeout=4) as response:
            return [m.get("name") for m in json.load(response).get("models", []) if m.get("name")]
    except Exception:
        return []


def catalog():
    if not available():
        return {"available": False, "pack_url": PACK_URL}
    writer = _cls(WRITER)
    writer_schema = _schema(writer, WRITER_KEYS)
    if "num_ctx" in writer_schema:  # video analysis + several pictures overflow the pack's 8192
        writer_schema["num_ctx"]["default"] = max(16384, int(writer_schema["num_ctx"].get("default") or 0))
    base = str(writer_schema.get("ollama_url", {}).get("default") or "http://127.0.0.1:11434")
    live = _ollama_models(base)
    if live and "model" in writer_schema:
        writer_schema["model"]["options"] = live
        vision = writer_schema.get("vision_model")
        if vision:
            first = [o for o in vision.get("options", []) if str(o).startswith("(")]
            vision["options"] = first + live
    return {"available": True, "settings": _schema(_cls(SETTINGS), SETTING_KEYS),
            "writer": writer_schema, "ollama": bool(live)}


def _director_graph(body):
    director = body.get("director") or {}
    node_id = str(director.get("id") or "director")
    return node_id, {node_id: {"class_type": "DirectorPlusTimeline", "inputs": {
        "mode": director.get("mode") or "REF2VA",
        "duration": float(director.get("duration") or 5),
        "timeline_data": director.get("timeline_data") or "{}",
        "builder_state": director.get("builder_state") or "{}",
    }}}


def brief(body):
    shots = body.get("shots") or {}
    settings = {k: v for k, v in (body.get("settings") or {}).items() if k in SETTING_KEYS}
    values = _cls(BUILDER)().run(json.dumps(shots, ensure_ascii=False), json.dumps(settings, ensure_ascii=False))
    if isinstance(values, dict):
        values = values.get("result", values)
    return dict(zip(("brief", "spec", "report"), values))


def write(body):
    from .. import prompt_director_compat
    prompt_director_compat.apply()  # Director Plus lookup, video analysis and sound rules
    built = brief(body)
    cls = _cls(WRITER)
    node_id, graph = _director_graph(body)
    kw = _defaults(cls)
    kw.update({k: v for k, v in (body.get("writer") or {}).items() if k in WRITER_KEYS and v not in (None, "")})
    shots = (body.get("shots") or {}).get("shots") or []
    kw.update(brief=built["brief"], spec=built["spec"], mode="FOLLOW_DIRECTOR",
              duration=float((body.get("director") or {}).get("duration") or 5), shot_count=len(shots),
              link_to_director=True, director_node_id=node_id, graph_prompt=graph,
              keep_alive="0", unload_after=True)
    params = inspect.signature(cls.run).parameters
    if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        kw = {k: v for k, v in kw.items() if k in params}
    started = time.time()
    result = cls().run(**kw)
    if isinstance(result, dict):
        result = result.get("result", result)
    names = getattr(cls, "RETURN_NAMES", ("prompt", "mode", "report", "duration", "raw"))
    out = dict(zip(names, result))
    return {"prompt": out.get("prompt", ""), "report": out.get("report", ""), "mode": out.get("mode", ""),
            "brief": built["brief"], "brief_report": built.get("report", ""), "seconds": round(time.time() - started, 1)}


def revise(body):
    writer = body.get("writer") or {}
    result = _cls(FREEZE)().run(str(body.get("prompt") or ""), revise=str(body.get("request") or ""),
                                revise_url=str(writer.get("ollama_url") or ""), revise_model=str(writer.get("model") or ""))
    applied = isinstance(result, dict)
    values = result.get("result") if applied else result
    return {"prompt": values[0], "report": values[1], "previous": values[2] if len(values) > 2 else "", "applied": applied}


def register_routes(server):
    from aiohttp import web

    @server.routes.get("/director_plus/prompt_studio/catalog")
    async def catalog_route(_request):
        return web.json_response(await asyncio.to_thread(catalog))

    async def run(request, job, needs_gpu):
        if _busy.locked():
            return web.json_response({"ok": False, "error": "다른 작성이 진행 중입니다."}, status=409)
        if not available():
            return web.json_response({"ok": False, "error": f"PromptDirector가 설치돼 있지 않습니다. ({PACK_URL})"}, status=400)
        if needs_gpu and server.prompt_queue.get_tasks_remaining() > 0:
            return web.json_response({"ok": False, "error": "영상 생성이 끝난 뒤 다시 시도하세요. (생성 중에는 VRAM이 부족합니다)"}, status=409)
        async with _busy:
            try:
                body = await request.json()
                if needs_gpu:  # the LLM gets the card to itself, as Prompt Forge did
                    comfy.model_management.unload_all_models()
                    comfy.model_management.soft_empty_cache()
                return web.json_response({"ok": True, **(await asyncio.to_thread(job, body))})
            except Exception as exc:  # another pack's code: always report, never a bare 500
                logging.exception("[Director Plus] Prompt Studio failed")
                return web.json_response({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=500)

    @server.routes.post("/director_plus/prompt_studio/brief")
    async def brief_route(request):
        return await run(request, brief, False)

    @server.routes.post("/director_plus/prompt_studio/write")
    async def write_route(request):
        return await run(request, write, True)

    @server.routes.post("/director_plus/prompt_studio/revise")
    async def revise_route(request):
        return await run(request, revise, True)
