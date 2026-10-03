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
MAX_TOKENS_DEFAULT = 4096
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
    if "max_tokens" in writer_schema:  # the pack's 1200 cuts a video-analysed prompt mid-description
        writer_schema["max_tokens"]["default"] = max(MAX_TOKENS_DEFAULT, int(writer_schema["max_tokens"].get("default") or 0))
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


def _soundtrack_fields(prompt):
    """With the sound checkboxes off the writer is told to write N/A for both sound fields, while a
    V+A reference's soundtrack rule says to follow <Audio n>. Turning the boxes off is meant to drop
    the style preset's invented ambience/score, not the reference sound, so an N/A next to a
    fully_copy soundtrack is replaced by the soundtrack sentence."""
    import re
    match = re.search(r"<Audio (\d+)>[^\n]*fully[ _]cop", prompt)  # "<Audio 1>: fully_copy" or "... fully copied ..."
    if not match:
        return prompt, False
    n = match.group(1)
    lines = {
        "overall_soundscape": f"The soundtrack follows <Audio {n}> (fully_copy): keep its ambience, sound effects and their "
                              "timing in sync with the matching actions, and do not invent sounds, dialogue or effects that are not in it.",
        "non_diegetic_music": f"follow <Audio {n}> (fully_copy) — keep any music it contains and add none.",
    }
    changed = False
    for field, text in lines.items():
        prompt, count = re.subn(rf"(?mi)^({field}\s*:)[ \t]*N/?A\.?[ \t]*$", lambda m: f"{m.group(1)} {text}", prompt)
        changed |= bool(count)
    return prompt, changed


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
    report = str(out.get("report", ""))
    # When the reply runs out of max_tokens the last sections never get written and the pack's
    # auto-fix fills them with N/A, which looks like the sound checkboxes were off.
    out["truncated"] = "was empty — set to N/A" in report
    out["prompt"], fixed = _soundtrack_fields(str(out.get("prompt", "")))
    if fixed:
        out["report"] = report + "\nDirector Plus: overall_soundscape / non_diegetic_music N/A → follow the V+A reference soundtrack (fully_copy)."
    return {"truncated": out["truncated"], "max_tokens": kw.get("max_tokens"), "prompt": out.get("prompt", ""), "report": out.get("report", ""), "mode": out.get("mode", ""),
            "brief": built["brief"], "brief_report": built.get("report", ""), "seconds": round(time.time() - started, 1)}


def revise(body):
    writer = body.get("writer") or {}
    result = _cls(FREEZE)().run(str(body.get("prompt") or ""), revise=str(body.get("request") or ""),
                                revise_url=str(writer.get("ollama_url") or ""), revise_model=str(writer.get("model") or ""))
    applied = isinstance(result, dict)
    values = result.get("result") if applied else result
    return {"prompt": values[0], "report": values[1], "previous": values[2] if len(values) > 2 else "", "applied": applied}


# ---------------------------------------------------------------- conversational editing
# Follows MMH3 Studio's studio_chat (MIT, Bokuwako): each turn sends the rules, a checklist of
# pitfalls, the production setup, the current prompt in full and the recent conversation. The model
# answers with a short Korean explanation and, when it changes something, the WHOLE prompt between
# markers. Nothing is applied here; the window puts it into the result box on the user's click.
PROMPT_OPEN, PROMPT_CLOSE = "<<<PROMPT", "PROMPT>>>"

CHAT_RULES = f"""You are the prompt editor for MiniMax H3 video prompts, working with the user in a conversation.
Answer in Korean. Be brief: at most six short lines of explanation.
When the user reports a problem, first say in one or two lines what in the prompt causes it.
When you change the prompt, output the WHOLE prompt again, every section, between a line containing only {PROMPT_OPEN} and a line containing only {PROMPT_CLOSE}.
Keep everything the user did not ask to change exactly as it is, word for word. Keep the section structure and headings.
Keep reference tags exactly as written (<Picture n>, <Video n>, <Audio n>, <RefMod n>) and never invent new reference numbers.
If the user only asks a question, answer it and do not output a prompt block.
After the prompt block, list what you changed as short bullet points."""

CHAT_CHECKLIST = """Known MiniMax H3 pitfalls. Check the prompt against every one of them.
1. A state written in the present tense is drawn immediately and for the whole clip.
   "She sits in the left chair" makes a seated ghost appear even while she is standing.
   Give only positions and ownership in shared blocks; put postures and changes into the shot text with a timestamp.
2. When the clip continues a previous scene, its opening frames are the previous scene's last frames (length in the setup below).
   [Shot 1] must continue that final state; new events and cuts go after that carried span.
3. POV is first-person through the named observer's eyes, at the eye height of their actual posture. Gaze is separate.
   Do not turn a camera-only change into a change of physical pose or gaze.
4. Left and right belong to the shot they are written in. When the camera side changes, say who is on whose side.
5. Dialogue must fit the time: Japanese runs about 6-7 morae per second. Give each line a start time and say that nobody speaks afterwards, or the model fills the gap with talk.
6. If two things move, give them different axes or rhythms, or they read as one motion.
7. Keep every cut time in one place: the [Shot N] header. Never write a second time.
8. When something must be absent, state the empty state plainly in the shot where it matters.
9. A reference governs only the attributes of its role (face, outfit, whole character, camera, motion). Say they follow the reference
   and describe only the changes the user asked for. Do not guess what the reference shows.
10. overall_soundscape holds ambience and physical sounds only. Every voice (lines, humming, whispers, laughter, breathing)
    goes on the shot timeline at its time; a voice written in the soundscape fills the gaps between lines.
11. A repeated or ongoing action must be written as continuing until the end of the clip, or the model stops it or returns to the starting pose."""


def chat_settings(source):
    source = source if isinstance(source, dict) else {}
    model = str(source.get("model") or "").strip()
    if not model:
        raise ValueError("대화 모델을 고르세요.")

    def number(key, default, low, high, integer=False):
        try:
            value = float(source.get(key, default))
        except (TypeError, ValueError):
            raise ValueError(f"대화 설정 {key} 값이 잘못되었습니다.")
        if not low <= value <= high:
            raise ValueError(f"대화 설정 {key} 값이 허용 범위를 벗어났습니다.")
        return int(value) if integer else value

    return {"model": model, "think": bool(source.get("think", False)),
            "history_turns": number("history_turns", 6, 0, 30, True),
            "options": {"temperature": number("temperature", 0.3, 0, 2),
                        "num_ctx": number("num_ctx", 16384, 2048, 131072, True),
                        "num_predict": number("num_predict", -1, -1, 32768, True)}}


def split_reply(text):
    """(explanation, prompt or None) from a reply containing the marker block."""
    import re
    match = re.search(re.escape(PROMPT_OPEN) + r"\s*\n(.*?)\n\s*" + re.escape(PROMPT_CLOSE), text, re.S)
    if not match:
        return text.strip(), None
    return re.sub(r"\n{3,}", "\n\n", text[:match.start()] + "\n" + text[match.end():]).strip(), match.group(1).strip()


def _setup_text(ctx):
    lines = [f"Engine: Director Plus, generation mode {ctx.get('mode') or 'REF2VA'}. "
             f"The prompt is for ONE clip of {float(ctx.get('duration') or 5):.3f} seconds (24 fps); "
             "the last timestamp is the clip end, never later."]
    scene = ctx.get("scene")
    if scene:
        frames = int(scene.get("context_frames") or 0)
        lines.append(f"This is scene {scene['index'] + 1} of {scene['count']} of a long video.")
        if scene["index"] > 0 and frames:
            lines.append(f"Its opening {frames} frames ({frames / 24:.2f} s) are the previous scene's last frames: "
                         "[Shot 1] continues that state; new events, dialogue and cuts start after that span.")
        if scene.get("previous_prompt"):
            lines.append("Previous scene prompt (for continuity only, do not copy):\n" + str(scene["previous_prompt"])[:4000])
    refs = ctx.get("references") or []
    if refs:
        lines.append("References on the timeline: " + "; ".join(str(r) for r in refs) + ".")
    if ctx.get("brief"):
        lines.append("The user's shot brief (what the prompt was written from):\n" + str(ctx["brief"])[:6000])
    return "\n".join(lines)


def chat(body):
    message = str(body.get("message") or "").strip()
    if not message:
        raise ValueError("메시지를 입력하세요.")
    llm = chat_settings(body.get("llm"))
    prompt = str(body.get("prompt") or "").strip()
    system = "\n\n".join([CHAT_RULES, CHAT_CHECKLIST, _setup_text(body.get("context") or {})])
    history = []
    recent = (body.get("history") or [])[-llm["history_turns"] * 2:] if llm["history_turns"] else []
    for m in recent:
        if m.get("role") not in ("user", "assistant"):
            continue
        content = str(m.get("content") or "")
        if m["role"] == "assistant":  # the current prompt below is the only copy the model should edit
            content = split_reply(content)[0] or "(프롬프트를 수정했음)"
        history.append({"role": m["role"], "content": content})
    current = (f"Current prompt:\n{PROMPT_OPEN}\n{prompt}\n{PROMPT_CLOSE}" if prompt else "There is no prompt yet.")
    messages = [{"role": "system", "content": system}] + history + \
               [{"role": "user", "content": current + "\n\nUser request:\n" + message}]
    base = str(body.get("ollama_url") or "http://127.0.0.1:11434").rstrip("/")
    payload = {"model": llm["model"], "messages": messages, "stream": False, "think": llm["think"],
               "keep_alive": "10m", "options": llm["options"]}
    started = time.time()
    req = urlrequest.Request(base + "/api/chat", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=900) as response:
            data = json.load(response)
    except Exception as exc:
        raise RuntimeError(f"Ollama 연결 실패: {exc}")
    if data.get("error"):
        raise RuntimeError("Ollama: " + str(data["error"]))
    reply = ((data.get("message") or {}).get("content") or "").strip()
    explanation, new_prompt = split_reply(reply)
    return {"reply": reply, "explanation": explanation, "prompt": new_prompt, "seconds": round(time.time() - started, 1)}


def chat_unload(body):
    base = str(body.get("ollama_url") or "http://127.0.0.1:11434").rstrip("/")
    model = str(body.get("model") or "")
    if model:
        req = urlrequest.Request(base + "/api/generate", data=json.dumps({"model": model, "keep_alive": 0}).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            urlrequest.urlopen(req, timeout=10).read()
        except Exception:
            pass
    return {}


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
                if needs_gpu:  # the LLM gets the card to itself
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

    @server.routes.post("/director_plus/prompt_studio/chat")
    async def chat_route(request):
        return await run(request, chat, True)

    @server.routes.post("/director_plus/prompt_studio/chat_unload")
    async def chat_unload_route(request):
        try:
            return web.json_response({"ok": True, **(await asyncio.to_thread(chat_unload, await request.json()))})
        except Exception as exc:
            return web.json_response({"ok": False, "error": str(exc)}, status=500)
