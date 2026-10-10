"""Long video: match the colour of scenes 2+ to scene 1 in the final MP4.

Chained Motion Context scenes slowly drift in colour (each scene inherits the
previous scene's tail, small errors add up). This is an output-only correction:
generation and the scene cache are untouched; only the saved video is re-encoded.

Per scene, the per-channel mean and standard deviation of its "settled" frames
(after the inherited context window) are measured, and an affine map per channel
(x * gain + offset) brings them to scene 1's values. The map ramps in over the
context window at the start of each scene so seams do not jump. Scenes with a
manual colour adjustment on their card are left as the user set them.
"""
import logging
import os
import subprocess
import uuid
from pathlib import Path

import numpy as np

from . import motion_context_disk as mc

GAIN_LIMITS = (0.8, 1.25)
OFFSET_LIMIT = 25.0
STAT_STRIDE = 4  # pixel stride for statistics (speed; statistics barely change)


def _span_index(t, spans):
    for i, (start, end) in enumerate(spans):
        if start <= t < end:
            return i
    return len(spans) - 1


def _measure(path, spans, settle_seconds):
    import av

    sums = [[np.zeros(3), np.zeros(3), 0] for _ in spans]
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 24.0)
        for i, frame in enumerate(container.decode(stream)):
            t = i / fps
            k = _span_index(t, spans)
            if k > 0 and t < spans[k][0] + settle_seconds:
                continue  # inherited context frames still look like the previous scene
            a = frame.to_ndarray(format="rgb24")[::STAT_STRIDE, ::STAT_STRIDE].reshape(-1, 3).astype(np.float64)
            sums[k][0] += a.mean(0)
            sums[k][1] += a.std(0)
            sums[k][2] += 1
    return [(m / n, s / n) if n else None for m, s, n in sums], fps


def _params(stats, skip):
    """Per-scene (gain[3], offset[3]); scene 1 and skipped scenes get identity."""
    identity = (np.ones(3), np.zeros(3))
    if not stats or stats[0] is None:
        return [identity for _ in stats]
    ref_mean, ref_std = stats[0]
    out = [identity]
    for k, st in enumerate(stats[1:], start=1):
        if st is None or k in skip:
            out.append(identity)
            continue
        mean, std = st
        gain = np.clip(ref_std / np.maximum(std, 1e-3), *GAIN_LIMITS)
        offset = np.clip(ref_mean - gain * mean, -OFFSET_LIMIT, OFFSET_LIMIT)
        out.append((gain, offset))
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
    stats, fps = _measure(path, spans, settle_seconds)
    params = _params(stats, skip)
    if all(np.allclose(g, 1) and np.allclose(o, 0) for g, o in params):
        return None

    ramp = max(1e-3, float(settle_seconds))

    def frame_params(t):
        k = _span_index(t, spans)
        gain, offset = params[k]
        if k > 0:
            w = min(1.0, max(0.0, (t - spans[k][0]) / ramp))
            pg, po = params[k - 1]
            gain, offset = pg + (gain - pg) * w, po + (offset - po) * w
        return gain.astype(np.float32), offset.astype(np.float32)

    ffmpeg = mc._find_ffmpeg()
    encoder = mc._preferred_h264_ffmpeg(ffmpeg)
    tmp = path.with_name(path.stem + f".color_{uuid.uuid4().hex[:8]}" + path.suffix)
    log_path = mc._ensure_cache_root() / f"_color_anchor_{uuid.uuid4().hex[:10]}.log"
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            width, height = stream.codec_context.width, stream.codec_context.height
            cmd = [
                encoder, "-y",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", f"{fps:.6f}", "-i", "-",
                "-i", str(path),
                "-map", "0:v:0", "-map", "1:a?",
                "-map_metadata", "1",
                *mc._h264_encode_args(encoder, crf, "fast"),
                "-c:a", "copy",
                "-movflags", "use_metadata_tags+faststart",
                str(tmp),
            ]
            with open(log_path, "wb") as log_f:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_f)
                try:
                    for i, frame in enumerate(container.decode(stream)):
                        gain, offset = frame_params(i / fps)
                        a = frame.to_ndarray(format="rgb24").astype(np.float32)
                        a = np.clip(a * gain + offset, 0, 255).astype(np.uint8)
                        proc.stdin.write(a.tobytes())
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

    parts = []
    for k, (gain, offset) in enumerate(params[1:], start=2):
        if k - 1 in skip:
            parts.append(f"scene {k} skipped (manual colour)")
        else:
            parts.append(f"scene {k} gain " + "/".join(f"{x:.3f}" for x in gain) +
                         " offset " + "/".join(f"{x:+.1f}" for x in offset))
    return "; ".join(parts)


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
