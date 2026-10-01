"""RefMod (pre-encoded reference) support for Director long video.

The single-video path hands RefMods to the DaSiWa Director Guide. Long video runs
through the Extender engine instead, so this module does the same conversion there:
the stored latents become native H3 reference blocks, and their decoded pixels are
shown to the text encoder. Tags stay as ``<RefMod N>`` until each scene knows how
many ordinary references it has, then become that scene's native labels.
"""
import hashlib
import os
import re

from ..director.helper_refmod_format import _safetensors_path, find_mod_path

REFMOD_TAG = re.compile(r"<\s*refmod\s*_?\s*(\d+)(?:\s*:[^>]+)?\s*>", re.I)
LABELS = {"image": "Picture", "video": "Video", "audio": "Audio"}
MARKER = "_director_refmod"  # LBH / audio regen keep these blocks at their stored size
_HASHES = {}


def active_rows(rows):
    """Enabled RefMod rows with a file and non-zero strength, by slot."""
    active = []
    for row in rows or []:
        if not isinstance(row, dict) or row.get("enabled", True) is False or not row.get("name"):
            continue
        try:
            strength = float(row.get("strength", 1))
        except (TypeError, ValueError):
            continue
        if strength != 0:
            active.append({"slot": int(row.get("slot")), "name": row["name"], "strength": strength})
    return sorted(active, key=lambda row: row["slot"])


def file_path(name):
    return _safetensors_path(find_mod_path(name))


def content_hash(name):
    """SHA-256 of the RefMod file; cached per (path, mtime, size)."""
    path = file_path(name)
    stat = os.stat(path)
    key = (os.path.normcase(os.path.abspath(path)), stat.st_mtime_ns, stat.st_size)
    if key not in _HASHES:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        _HASHES[key] = digest.hexdigest()
    return _HASHES[key]


def signature(rows):
    """Cache identity of the selected RefMods: content, not name or mtime, so a
    project restored under another file name keeps its cache."""
    return [[row["slot"], content_hash(row["name"]), round(row["strength"], 6)] for row in active_rows(rows)]


def rows_from_items(items):
    """One row per slot from the guide's loaded RefMod items (bundles repeat a slot)."""
    rows = {}
    for item in items or []:
        rows.setdefault(int(item["slot"]), {"slot": int(item["slot"]), "name": item["name"],
                                            "strength": float(item.get("strength", 1))})
    return list(rows.values())


def prepare(items, vae):
    """Decode each RefMod once: tokenizer item (pixels) + native reference block."""
    prepared = []
    for item in items or []:
        kind = item["kind"]
        latent = item["latent"]
        if kind == "audio":
            prepared.append({"slot": int(item["slot"]), "kind": "audio", "item": {"type": "audio"},
                             "block": {"kind": "audio", "ref_audio_t": int(item.get("latent_t", 0) or latent.shape[-1]),
                                       "audio_latent": latent, MARKER: True}})
            continue
        pixels = vae.decode(latent)
        if getattr(pixels, "ndim", 0) == 5 and pixels.shape[0] == 1:
            pixels = pixels[0]
        if getattr(pixels, "ndim", 0) != 4 or pixels.shape[-1] != 3:
            raise ValueError("Director long video: connect the MiniMax H3 video VAE (invalid decoded RefMod shape).")
        is_video = kind == "video" or (getattr(latent, "ndim", 0) >= 5 and latent.shape[2] > 1)
        if is_video:
            block = {"kind": kind, "latent": latent, "latent_t": latent.shape[2], "latent_h": latent.shape[3],
                     "latent_w": latent.shape[4], "ref_audio_t": 0, "audio_latent": None}
        else:
            block = {"kind": "image", "latent": latent, "latent_h": latent.shape[3], "latent_w": latent.shape[4]}
        block[MARKER] = True
        prepared.append({"slot": int(item["slot"]), "kind": "video" if is_video else "image",
                         "item": {"type": "video" if is_video else "image", "data": pixels.cpu().clone()},
                         "block": block})
    return prepared


def append(ref_items, ref_blocks, prepared):
    """Append after the scene's own references (native order) and return slot -> labels."""
    counts = {kind: sum(1 for item in ref_items if isinstance(item, dict) and item.get("type") == kind)
              for kind in LABELS}
    tags = {}
    for entry in prepared:
        counts[entry["kind"]] += 1
        ref_items.append(entry["item"])
        ref_blocks.append(entry["block"])
        tags.setdefault(entry["slot"], []).append(f"<{LABELS[entry['kind']]} {counts[entry['kind']]}>")
    return {slot: " ".join(labels) for slot, labels in tags.items()}


def translate(prompt, tags):
    def replace(match):
        slot = int(match.group(1))
        if slot not in tags:
            active = ", ".join(f"<RefMod {number}>" for number in sorted(tags)) or "없음"
            raise ValueError(f"프롬프트의 <RefMod {slot}>에 켜진 RefMod가 없습니다 (켜진 슬롯: {active}). "
                             f"SAVED REFERENCES에서 {slot}번 슬롯에 RefMod를 선택하거나, 프롬프트 태그 번호를 켜진 슬롯에 맞추세요.")
        return tags[slot]
    return REFMOD_TAG.sub(replace, str(prompt))
