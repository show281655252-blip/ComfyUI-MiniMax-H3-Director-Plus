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
import functools
import importlib
import io
import logging
import os
import re
import time

STEP_SECONDS = 0.5      # clips longer than MAX_FRAMES * FINE_STEP
FINE_STEP = 0.25        # short clips: back-and-forth actions (sweeping, waving) alias at 0.5 s
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
TIMELINE: one line per phase of action, "From X s to Y s: ...". A phase is a run of frames showing one movement; merge consecutive frames into one phase instead of writing a line for every frame, and never repeat the same sentence for several phases. Compare each frame with the next one before writing. For every change name the hand as the performer's own left/right AND its screen side, give the exact hand and finger shape (count the extended fingers), where the hand is relative to the face and body, torso lean and weight shift, head tilt, gaze, eyes (blinks), mouth shape and expression, and any visual effect (when it appears, its size, position, movement and when it leaves).
HELD OBJECTS: if the performer holds or uses an object (broom, sword, cup, phone ...), note in every frame where its working end is (screen left / centre / right, near / far) and describe how it moves between frames (e.g. "the broom head sweeps from screen right to screen left").
CONTINUOUS ACTIONS: write repeated or continuous actions (sweeping, walking, waving, rocking, dancing) as that action with its rhythm (e.g. "sweeps left and right about once per second"); never break them into grip/release steps. Write "hold" only when neither the body nor the object moves between the two frames.
END ({last}): describe the last frame on its own (pose, lean, hands, object position, gaze, expression), then say how it differs from START. If the action is still going on in the last frames, say it continues to the last frame without slowing down, settling or returning to the start pose.
BACKGROUND / PROPS / LIGHTING: one short line, and note any change.
Be terse and exact. No markdown headings other than the part names."""


def set_writer_args(kwargs):
    return _writer_args.set(kwargs)


def reset_writer_args(token):
    _writer_args.reset(token)


def _step_for(path, start, end):
    if end is None:
        import av
        with av.open(path) as container:
            end = float(container.duration or 0) / 1_000_000
    return FINE_STEP if (end - start) <= MAX_FRAMES * FINE_STEP + 1e-6 else STEP_SECONDS


def _sample_frames(path, start, end, step):
    import av
    from PIL import Image

    targets = [start + i * step for i in range(MAX_FRAMES)]
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
        return (*_cache[key], True)
    step = _step_for(path, start, end)
    times, images = _sample_frames(path, start, end, step)
    if not images:
        raise ValueError("no frames could be read")
    labels = ", ".join(f"image {i + 1} = {t:.2f} s" for i, t in enumerate(times))
    text = client.chat(
        base_url=args.get("ollama_url") or "http://127.0.0.1:11434", model=model, system=SYSTEM,
        user=QUESTION.format(step=step, labels=labels, first=f"{times[0]:.2f} s", last=f"{times[-1]:.2f} s"),
        images=images, options={"temperature": 0.1, "top_p": 0.8, "num_predict": 1800,
                                "num_ctx": max(8192, int(args.get("num_ctx") or 8192))},
        keep_alive="0" if split else (args.get("keep_alive") or "5m"))
    text = re.sub(r"(?s)<think>.*?</think>", "", str(text or "")).strip()
    if not text:
        raise ValueError("the model returned nothing")
    _cache[key] = (text, step)
    return text, step, False


def _video_items(link, prompt_graph, node_id_hint):
    """Video items in the order reference_labels numbers them (<Video 1>, <Video 2>, ...)."""
    _nid, node, _note = link.find_director(prompt_graph, node_id_hint)
    if not node:
        return []
    _images, others = link.parse_timeline(link._widget_value(node, "timeline_data"))
    return [item for item in others if item.get("type") == "video"
            and item.get("media_mode", "video") in ("video", "video_audio")]


def _has_audio(path):
    try:
        import av
        with av.open(path) as container:
            return bool(container.streams.audio)
    except Exception:
        return True


def _drop_silent_soundtracks(link, labels, videos, notes):
    """A V+A item on a clip without sound is generated as V only (director/timeline.py), so the
    writer must not get an <Audio n> soundtrack label for it; later audio labels shift down."""
    silent = set()
    for number, item in enumerate(videos, 1):
        if item.get("media_mode") == "video_audio":
            path = link.resolve_media_path(item.get("value"))
            if path and not _has_audio(path):
                silent.add(number)
    if not silent:
        return labels
    kept = [label for label in labels
            if not any(re.match(rf"<Audio \d+>: soundtrack of <Video {n}>", str(label)) for n in silent)]
    counter = iter(range(1, len(kept) + 1))
    kept = [re.sub(r"^<Audio \d+>:", lambda _m: f"<Audio {next(counter)}>:", str(label))
            if str(label).startswith("<Audio ") else label for label in kept]
    notes.append("Director Plus: " + ", ".join(f"<Video {n}>" for n in sorted(silent))
                 + " is set to V+A but has no sound — used as video only.")
    return kept


SOUNDTRACK_RULE = (
    "SOUND RULE for <Audio {n}> (the reference video's own soundtrack, V+A): in retention_analysis mark "
    "<Audio {n}> fully_copy. In overall_soundscape write that the soundtrack follows <Audio {n}> (fully_copy): "
    "keep its ambience, sound effects and their timing in sync with the matching actions, and do not invent "
    "sounds, dialogue or effects that are not in it. In non_diegetic_music write: follow <Audio {n}> "
    "(fully_copy) — keep any music it contains and add none. Do not write N/A for these two fields.")


VOICE_RULE = (
    "VOICE RULE for <Audio {n}> (a separate audio file, not a video soundtrack): if it is a speaker's voice, "
    "bind it with these exact forms. In subject_definitions, end that speaker's Subject with: <Audio {n}> is the "
    "voice-timbre reference for <Subject K> (SX). In retention_analysis write: <Audio {n}>: reference. <Audio {n}> is "
    "the voice-timbre reference for <Subject K> (SX); the spoken words come only from the dialogue line. At every "
    "line that voice speaks write: <Subject K> (SX) says in <delivery>, in the voice timbre referenced from "
    "<Audio {n}>: <d>[Language] ...</d>. and end that sentence with a period after </d>. Never write what "
    "<Audio {n}> sounds like (no tone, pitch, timbre or style words right after the label), never mark it fully_copy, "
    "and never mention speech, dialogue, voices or vocal sounds in overall_soundscape — speech belongs only in "
    "detailed_description. The speaker is on screen: do not turn the line into an off-screen voiceover.")


def _soundtrack_rules(labels):
    """Tell the writer to take a V+A soundtrack as it is instead of describing new sounds, and to bind a
    separate audio file (audio item or a video used as A) the way the spec wants a voice reference bound."""
    out = []
    for label in labels:
        text = str(label)
        match = re.match(r"<Audio (\d+)>: soundtrack of <Video \d+>", text)
        if match:
            out.append(f"{label}\n{SOUNDTRACK_RULE.format(n=match.group(1))}")
            continue
        match = re.match(r"<Audio (\d+)>: ", text)
        out.append(f"{label}\n{VOICE_RULE.format(n=match.group(1))}" if match else label)
    return out


def fix_summary_bracket(prompt):
    """REF2VA summary must open with a bracketed task type ("[reference generation]"); the writer often
    leaves the brackets off. Wrap the first summary line when it is a short task name. Returns (text, fixed)."""
    match = re.search(r"(?mi)^(summary\s*:)[ \t]*(.*)$", prompt or "")
    if not match:
        return prompt, False
    rest = match.group(2).strip()
    if rest:  # "summary: task" -> "summary:\n[task]"
        begin, end, lead = match.end(1), match.end(2), "\n"
    else:     # task type on the next non-empty line
        nxt = re.match(r"\s*\n[ \t]*([^\n]*)", prompt[match.end():])
        if not nxt:
            return prompt, False
        rest = nxt.group(1).strip()
        begin, end, lead = match.end() + nxt.start(1), match.end() + nxt.end(1), ""
    if not rest or rest.startswith("[") or "<" in rest or ":" in rest or len(rest) > 80:
        return prompt, False
    return prompt[:begin] + f"{lead}[{rest.rstrip('.')}]" + prompt[end:], True


def wrap_read_director(link):
    original = link.read_director
    if getattr(original, "_director_plus_video", False):
        return False
    client = importlib.import_module(link.__name__.rsplit(".", 1)[0] + ".ollama_client")

    @functools.wraps(original)
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
        labels = _drop_silent_soundtracks(link, list(out.get("other_labels") or []), videos, out["notes"])
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
                text, step, cached = _analyse(client, writer, path, start, end)
            except Exception as exc:  # the writer must still run without it
                out["notes"].append(f"Director Plus video analysis: <Video {number}> failed ({exc}); "
                                    "the writer gets the label only.")
                continue
            name = os.path.basename(str(item.get("value") or ""))
            labels[index] = (f"<Video {number}>: {name} (video; not watched by the writer, but analysed "
                             f"from frames sampled every {step} s by a vision model)\n"
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
        out["other_labels"] = _soundtrack_rules(labels)
        return out

    read_director._director_plus_video = True
    link.read_director = read_director
    return True


# Same word list as PromptDirector's validator (_SPEECH_WORDS): speech belongs in detailed_description only.
_SPEECH = re.compile(r"(?i)\b(?:speak\w*|spoke\w*|spoken|say\w*|said|talk\w*|speech|conversation\w*|conversing|"
                     r"dialogue|dialog|chatter\w*|voices?|vocal\w*|sing\w*|sang|sung|whisper\w*|shout\w*|yell\w*|"
                     r"murmur\w*|mutter\w*|utter\w*|exclaim\w*|reply\w*|replies|replied)\b|\(S\d+\)")


def fix_soundscape_speech(prompt):
    """Drop the sentences of overall_soundscape that talk about speech ("No vocal sounds beyond the
    dialogue.", "a clear spoken line from (S1)"). Sentences that cite an <Audio n> (the V+A soundtrack
    rule) are kept, and the field is never emptied. Returns (text, removed sentences)."""
    match = re.search(r"(?mis)^(overall_soundscape\s*:)(.*?)(?=^\s*[a-z_]+\s*:|\Z)", prompt or "")
    if not match:
        return prompt, []
    body = match.group(2)
    sentences = re.split(r"(?<=[.!?;])\s+", body.strip())
    # the V+A rule's own sentence ("follows <Audio n> (fully_copy) ... do not invent ... dialogue") stays
    keep = [s for s in sentences if ("<Audio" in s and "fully" in s.lower()) or not _SPEECH.search(s)]
    dropped = [s for s in sentences if s not in keep]
    if not dropped or not keep:
        return prompt, []
    text = " ".join(keep)
    if text.endswith(";"):
        text = text[:-1] + "."
    trailing = body[len(body.rstrip()):]
    return prompt[:match.start(2)] + " " + text + trailing + prompt[match.end(2):], dropped


def _fix_writer_result(writer_class, result):
    """Apply the summary-bracket and soundscape-speech fixes to the writer's prompt output (tuple, or
    {"ui", "result"} dict) and note them in the report."""
    values = result.get("result") if isinstance(result, dict) else result
    if not isinstance(values, (tuple, list)) or not values:
        return result
    names = list(getattr(writer_class, "RETURN_NAMES", ("prompt", "mode", "report")))
    i_prompt = names.index("prompt") if "prompt" in names else 0
    text, bracket = fix_summary_bracket(str(values[i_prompt]))
    text, dropped = fix_soundscape_speech(text)
    if not bracket and not dropped:
        return result
    notes = (["Director Plus: summary task type wrapped in brackets."] if bracket else []) + \
            [f"Director Plus: removed speech from overall_soundscape: \"{s}\"" for s in dropped]
    values = list(values)
    values[i_prompt] = text
    if "report" in names and names.index("report") < len(values):
        i_report = names.index("report")
        values[i_report] = str(values[i_report]) + "\n" + "\n".join(notes)
    if isinstance(result, dict):
        out = dict(result)
        out["result"] = tuple(values)
        return out
    return tuple(values)


def wrap_writer(writer_class):
    original = writer_class.run
    if getattr(original, "_director_plus_video", False):
        return False

    @functools.wraps(original)  # keeps the signature callers inspect (Prompt Studio)
    def run(self, *args, **kwargs):
        token = set_writer_args(kwargs)
        try:
            result = original(self, *args, **kwargs)
        finally:
            reset_writer_args(token)
        try:
            return _fix_writer_result(writer_class, result)
        except Exception:  # never break the writer over a cosmetic fix
            logging.exception("[Director Plus] summary bracket fix skipped")
            return result

    run._director_plus_video = True
    writer_class.run = run
    return True
