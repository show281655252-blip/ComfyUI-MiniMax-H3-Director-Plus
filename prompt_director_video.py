"""Let the PromptDirector writer "see" Director video references.

The writer sends Director images to its Ollama vision model, but a video reference reaches
it only as a label ("<Video 1>: clip.mp4 (video; not viewed)"), so motion, timing and
expressions get guessed. Here each REF2VA video (its timeline trim range) is sampled every
0.5 s, the frames go to the writer's own Ollama model once, and the label is replaced with
the resulting motion timeline. The writer's guideline already allows describing content
that comes from "an actual analysis".

Applied by prompt_director_compat; nothing in the PromptDirector folder is modified.
"""
import base64
import contextvars
import importlib
import io
import logging
import os
import re
import time

STEP_SECONDS = 0.5
MAX_FRAMES = 30          # 15 s, H3's reference-video limit
FRAME_MAX_SIDE = 448
_writer_args = contextvars.ContextVar("director_plus_writer_args", default=None)
_cache = {}

SYSTEM = (
    "You are a frame-by-frame motion analyst for a video-generation prompt writer. You receive "
    "chronological frames sampled from ONE reference video. Report only what is observable: camera, "
    "staging, pose, motion, timing, hands, gaze, facial expression, visual effects. Never describe the "
    "performer's identity, hair, face design, body design, clothing or accessories, because the performer "
    "will be replaced by another character. Do not guess beyond the frames; write 'unclear' instead."
)

QUESTION = """Frames sampled every {step} s from one reference video, in order: {labels}.

Write a precise motion analysis in plain English with these parts:
CAMERA: fixed or moving; angle, height, distance; framing (which part of the body is visible); any zoom, pan, tilt or hard cut, with times.
START ({first}): pose, position of both arms and hands, head angle, gaze, eyes, mouth, expression.
TIMELINE: one line per span, "From X s to Y s: ...". Write "hold" spans explicitly. For every change name the hand as the performer's own left/right AND its screen side, give the exact hand and finger shape (count the extended fingers), where the hand is relative to the face and body, head tilt, gaze, eyes (blinks), mouth shape and expression, and any visual effect (when it appears, its size, position, movement and when it leaves).
END ({last}): final pose, hands, gaze and expression.
BACKGROUND / PROPS / LIGHTING: one short line, and note any change.
Be terse and exact. No markdown headings other than the part names."""


def set_writer_args(kwargs):
    return _writer_args.set(kwargs)


def reset_writer_args(token):
    _writer_args.reset(token)


def _sample_frames(path, start, end):
    import av
    from PIL import Image

    targets = [start + i * STEP_SECONDS for i in range(MAX_FRAMES)]
    targets = [t for t in targets if end is None or t <= end + 1e-6]
    picked = []
    with av.open(path) as container:
        stream = container.streams.video[0]
        for frame in container.decode(stream):
            if frame.time is None:
                continue
            while targets and frame.time + 1e-6 >= targets[0]:
                picked.append((targets.pop(0), frame.to_image()))
            if not targets:
                break
    images = []
    for index, (_t, image) in enumerate(picked):
        image = image.convert("RGB")
        # Ollama merges same-size images in one message into a video and keeps one frame;
        # a slightly different size per frame keeps every timestamp separate.
        side = FRAME_MAX_SIDE - index * 4
        scale = side / float(max(image.size))
        if scale < 1.0:
            image = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=90)
        images.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
    return [round(t - start, 2) for t, _image in picked], images


def _analyse(client, args, path, start, end):
    model = str(args.get("model") or "")
    vision_model = str(args.get("vision_model") or "").strip()
    if vision_model and not vision_model.startswith("("):
        model = vision_model
    split = model != str(args.get("model") or "")
    stat = os.stat(path)
    key = (path, stat.st_mtime, stat.st_size, start, end, model)
    if key in _cache:
        return _cache[key], True
    times, images = _sample_frames(path, start, end)
    if not images:
        raise ValueError("no frames could be read")
    labels = ", ".join(f"image {i + 1} = {t:.1f} s" for i, t in enumerate(times))
    text = client.chat(
        base_url=args.get("ollama_url") or "http://127.0.0.1:11434", model=model, system=SYSTEM,
        user=QUESTION.format(step=STEP_SECONDS, labels=labels, first=f"{times[0]:.1f} s", last=f"{times[-1]:.1f} s"),
        images=images, options={"temperature": 0.1, "top_p": 0.8, "num_predict": 1400,
                                "num_ctx": max(8192, int(args.get("num_ctx") or 8192))},
        keep_alive="0" if split else (args.get("keep_alive") or "5m"))
    text = re.sub(r"(?s)<think>.*?</think>", "", str(text or "")).strip()
    if not text:
        raise ValueError("the model returned nothing")
    _cache[key] = text
    return text, False


def _video_items(link, prompt_graph, node_id_hint):
    """Video items in the order reference_labels numbers them (<Video 1>, <Video 2>, ...)."""
    _nid, node, _note = link.find_director(prompt_graph, node_id_hint)
    if not node:
        return []
    _images, others = link.parse_timeline(link._widget_value(node, "timeline_data"))
    return [item for item in others if item.get("type") == "video"
            and item.get("media_mode", "video") in ("video", "video_audio")]


def wrap_read_director(link):
    original = link.read_director
    if getattr(original, "_director_plus_video", False):
        return False
    client = importlib.import_module(link.__name__.rsplit(".", 1)[0] + ".ollama_client")

    def read_director(prompt_graph, node_id_hint="", *args, **kwargs):
        out = original(prompt_graph, node_id_hint, *args, **kwargs)
        writer = _writer_args.get()
        if not writer or not out.get("found") or out.get("mode") != "REF2VA":
            return out
        try:
            videos = _video_items(link, prompt_graph, node_id_hint)
        except Exception as exc:
            out["notes"].append(f"Director Plus video analysis skipped: {exc}")
            return out
        labels = list(out.get("other_labels") or [])
        for number, item in enumerate(videos, 1):
            tag = f"<Video {number}>:"
            index = next((i for i, label in enumerate(labels) if str(label).startswith(tag)), None)
            path = link.resolve_media_path(item.get("value"))
            if index is None or not path:
                out["notes"].append(f"Director Plus video analysis: <Video {number}> file not found.")
                continue
            start = float(item.get("trim_start") or 0.0)
            end = item.get("trim_end")
            end = None if end is None else float(end)
            began = time.time()
            try:
                text, cached = _analyse(client, writer, path, start, end)
            except Exception as exc:  # the writer must still run without it
                out["notes"].append(f"Director Plus video analysis: <Video {number}> failed ({exc}); "
                                    "the writer gets the label only.")
                continue
            name = os.path.basename(str(item.get("value") or ""))
            labels[index] = (f"<Video {number}>: {name} (video; not watched by the writer, but analysed "
                             f"from frames sampled every {STEP_SECONDS} s by a vision model)\n"
                             f"ROLE OF <Video {number}>: it decides camera, framing, background, lighting, props, "
                             f"staging, pose, body and hand motion, gaze, expression timing and pacing. The pictures "
                             f"decide only who the character is and what she or he wears; ignore the pictures' own "
                             f"backgrounds and poses. The original performer of <Video {number}> is replaced; never "
                             f"carry over the performer's looks or clothing. Write detailed_description in time order "
                             f"from this analysis, keeping its timestamps, holds and hand shapes.\n"
                             f"MOTION ANALYSIS of <Video {number}>:\n{text}")
            out["notes"].append(f"Director Plus video analysis: <Video {number}> "
                                f"{'cached' if cached else f'{time.time() - began:.0f}s'}, {len(text)} chars.")
            logging.info("[Director Plus] Prompt Writer: <Video %d> motion analysis %s (%d chars).",
                         number, "from cache" if cached else f"in {time.time() - began:.0f}s", len(text))
        out["other_labels"] = labels
        return out

    read_director._director_plus_video = True
    link.read_director = read_director
    return True


def wrap_writer(writer_class):
    original = writer_class.run
    if getattr(original, "_director_plus_video", False):
        return False

    def run(self, *args, **kwargs):
        token = set_writer_args(kwargs)
        try:
            return original(self, *args, **kwargs)
        finally:
            reset_writer_args(token)

    run._director_plus_video = True
    writer_class.run = run
    return True
