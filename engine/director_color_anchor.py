"""Long video: match the colour of scenes 2+ to scene 1 in the final MP4.

Chained Motion Context scenes slowly drift in colour (each scene inherits the
previous scene's tail, small errors add up). This is an output-only correction:
generation and the scene cache are untouched; only the saved video is re-encoded.

Per scene, the per-channel mean of its near-neutral pixels (walls, stone, sky...;
vivid subject colours are left out so a character filling more or less of the
frame does not skew it) is measured on its "settled" frames, after the inherited
context window. A per-channel gain (white balance / exposure) brings each scene to
scene 1. The gain ramps in over the context window at the start of each scene so
seams do not jump. Scenes with a manual colour adjustment on their card are left
as the user set them.

Frames go through ffmpeg as 16-bit RGB with accurate rounding: an 8-bit RGB round
trip alone darkens the video by about one level.
"""
import logging
import os
import subprocess
import uuid
from pathlib import Path

import numpy as np

from . import motion_context_disk as mc

GAIN_LIMITS = (0.85, 1.18)
STAT_STRIDE = 4          # pixel stride for statistics
NEUTRAL_CHROMA = 40.0    # max(R,G,B) - min(R,G,B) below this (8-bit scale) counts as near-neutral
NEUTRAL_MIN_SHARE = 0.03  # fewer neutral pixels than this -> use the whole frame
SWS = "accurate_rnd+full_chroma_int+bicubic"


def _span_index(t, spans):
    for i, (start, end) in enumerate(spans):
        if start <= t < end:
            return i
    return len(spans) - 1


def _frames(ffmpeg, path, width, height):
    """Decoded frames as float32 RGB in 0..255, from a 16-bit accurate conversion."""
    proc = subprocess.Popen(
        [ffmpeg, "-loglevel", "error", "-i", str(path), "-map", "0:v:0",
         "-f", "rawvideo", "-pix_fmt", "rgb48le", "-sws_flags", SWS, "-"],
        stdout=subprocess.PIPE,
    )
    size = width * height * 3 * 2
    try:
        while True:
            buf = proc.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint16).reshape(height, width, 3).astype(np.float32) * (255.0 / 65535.0)
    finally:
        proc.stdout.close()
        proc.wait()


def _measure(frames, fps, spans, settle_seconds):
    sums = [[np.zeros(3), 0] for _ in spans]
    for i, a in enumerate(frames):
        t = i / fps
        k = _span_index(t, spans)
        if k > 0 and t < spans[k][0] + settle_seconds:
            continue  # inherited context frames still look like the previous scene
        p = a[::STAT_STRIDE, ::STAT_STRIDE].reshape(-1, 3)
        chroma = p.max(1) - p.min(1)
        luma = p.mean(1)
        mask = (chroma < NEUTRAL_CHROMA) & (luma > 20) & (luma < 235)
        sel = p[mask] if mask.mean() >= NEUTRAL_MIN_SHARE else p
        sums[k][0] += sel.mean(0)
        sums[k][1] += 1
    return [m / n if n else None for m, n in sums]


LUMA = np.array([0.299, 0.587, 0.114])


def _gains(means, skip):
    """Per-scene gain[3]; scene 1 and skipped scenes get 1.

    Only the colour balance is matched: the gains are scaled so the scene keeps its own
    brightness. Measured brightness depends on what is in frame (more sunlit floor, a
    white costume ...), while the drift we correct is mainly a colour cast.
    """
    ones = np.ones(3)
    if not means or means[0] is None:
        return [ones for _ in means]
    out = [ones]
    for k, m in enumerate(means[1:], start=1):
        if m is None or k in skip:
            out.append(ones)
            continue
        g = means[0] / np.maximum(m, 1e-3)
        g *= float(LUMA @ m) / max(float(LUMA @ (m * g)), 1e-3)
        out.append(np.clip(g, *GAIN_LIMITS))
    return out


def anchor_to_first_scene(path, spans, skip=(), settle_seconds=22 / 24.0, crf=18):
    """Re-encode `path` in place with scenes 2+ colour-matched to scene 1.

    spans: [(start_s, end_s), ...] per scene in the final video.
    skip: scene indices to leave unchanged (e.g. manual colour adjustment).
    Returns a short log line, or None when nothing was done.
    """
    import av

    path = Path(path)
    spans = [(float(a), float(b)) for a, b in spans]
    if len(spans) < 2 or not path.is_file():
        return None
    skip = set(int(x) for x in skip)
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 24.0)
        width, height = stream.codec_context.width, stream.codec_context.height

    ffmpeg = mc._find_ffmpeg()
    gains = _gains(_measure(_frames(ffmpeg, path, width, height), fps, spans, settle_seconds), skip)
    if all(np.allclose(g, 1, atol=2e-3) for g in gains):
        return None

    ramp = max(1e-3, float(settle_seconds))

    def frame_gain(t):
        k = _span_index(t, spans)
        gain = gains[k]
        if k > 0:
            w = min(1.0, max(0.0, (t - spans[k][0]) / ramp))
            gain = gains[k - 1] + (gain - gains[k - 1]) * w
        return gain.astype(np.float32) * (65535.0 / 255.0)

    encoder = mc._preferred_h264_ffmpeg(ffmpeg)
    tmp = path.with_name(path.stem + f".color_{uuid.uuid4().hex[:8]}" + path.suffix)
    log_path = mc._ensure_cache_root() / f"_color_anchor_{uuid.uuid4().hex[:10]}.log"
    cmd = [
        encoder, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb48le", "-s", f"{width}x{height}", "-r", f"{fps:.6f}", "-i", "-",
        "-i", str(path),
        "-map", "0:v:0", "-map", "1:a?",
        "-map_metadata", "1",
        "-sws_flags", SWS,
        *mc._h264_encode_args(encoder, crf, "fast"),
        "-c:a", "copy",
        "-movflags", "use_metadata_tags+faststart",
        str(tmp),
    ]
    try:
        with open(log_path, "wb") as log_f:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_f)
            try:
                for i, a in enumerate(_frames(ffmpeg, path, width, height)):
                    out = np.clip(a * frame_gain(i / fps) + 0.5, 0, 65535).astype(np.uint16)
                    proc.stdin.write(out.tobytes())
            finally:
                proc.stdin.close()
                code = proc.wait()
        if code != 0:
            tail = log_path.read_bytes()[-4000:].decode("utf-8", errors="replace")
            raise RuntimeError(f"Director Plus colour anchor: ffmpeg failed ({code}).\n{tail}")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
        log_path.unlink(missing_ok=True)

    return "; ".join(
        f"scene {k} skipped (manual colour)" if k - 1 in skip else
        f"scene {k} gain " + "/".join(f"{x:.3f}" for x in g)
        for k, g in enumerate(gains[1:], start=2)
    )


def apply_if_enabled(path, long_video, color_timeline, crf=18):
    """Called by DirectorPlusVideoOutput after the final MP4 is written."""
    if not (long_video or {}).get("color_anchor"):
        return
    spans = [(s["start"], s["end"]) for s in color_timeline]
    skip = [s["index"] for s in color_timeline if s.get("modified")]
    try:
        context = int(str(long_video.get("context_length", "22")))
    except ValueError:
        context = 22
    note = anchor_to_first_scene(path, spans, skip, settle_seconds=context / 24.0, crf=crf)
    if note:
        logging.info("[Director Plus] Colour matched to scene 1: %s", note)
