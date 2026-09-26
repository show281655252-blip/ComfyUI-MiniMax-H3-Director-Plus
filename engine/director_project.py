# Modified for Director Plus isolation, 2026-09-26. See NOTICE.md for upstream attribution.
"""Portable Director projects using the Extender cache archive."""
import asyncio
import copy
import hashlib
import json
import shutil
import time
import uuid
import zipfile
from pathlib import Path

from aiohttp import web
import folder_paths
from server import PromptServer
from . import extender
from .motion_context_disk import _color_timeline, _comfy_media_item


def project_owner(state, widgets):
    width, height = extender._manual_effective_resolution(int(widgets["width"]), int(widgets["height"]))
    signature = json.dumps([None, width, height, state.get("context_length", "22")])
    return "director_" + state["project_id"] + "_" + hashlib.sha256(signature.encode()).hexdigest()[:12]


def build_project(payload, output):
    director = copy.deepcopy(payload)
    state = director["state"]
    long = state["long_video"]
    if long.get("start_mode") == "video":
        raise ValueError("Director .ext projects support new-video mode only.")
    if state.get("refmods"):
        raise ValueError("Remove RefMod references before saving a Director .ext project.")
    long.pop("last_preview", None)
    owner = long.get("cache_owner") or project_owner(long, director["widgets"])
    assets = []
    root = Path(folder_paths.get_input_directory()).resolve()
    for index, item in enumerate(state.get("items", [])):
        value = item.get("value")
        if item.get("type") not in ("image", "video", "audio") or not value:
            continue
        path = (root / value).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Director reference is missing or outside input: {value}")
        member = f"director_media/{index}{path.suffix.lower()}"
        assets.append((member, path))
        item["value"] = member
        item["thumbnail"] = None
    project = {
        "director": director,
        "extender": {"generation_mode": "ref2va", "motion_context": True,
                     "clips_json": json.dumps({"version": 2, "clips": long["clips"]}),
                     "refs_json": json.dumps({"version": 2, "refs": [None] * 9})},
    }
    meta = extender._build_project_archive(owner, "Director_Project.ext", project, output)
    with zipfile.ZipFile(output, "a", compression=zipfile.ZIP_STORED) as archive:
        for member, path in assets:
            archive.write(path, member)
    return meta


def _store_media(archive, member, suffix, media_root):
    """Copy one archived reference into a content-addressed file, reusing an identical copy.

    Loading the same project (or another project with the same pictures) repeatedly
    used to create a new folder each time; the hash name lets every load share one file.
    """
    temp = media_root / f".incoming_{uuid.uuid4().hex}{suffix}"
    digest = hashlib.sha256()
    try:
        with archive.open(member) as source, temp.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
                target.write(chunk)
        output = media_root / f"{digest.hexdigest()[:32]}{suffix}"
        if output.is_file() and output.stat().st_size == temp.stat().st_size:
            temp.unlink()
        else:
            temp.replace(output)
        return output
    finally:
        temp.unlink(missing_ok=True)


def restore_project(path):
    with zipfile.ZipFile(path) as archive:
        meta = json.loads(archive.read("project.json"))
        director = copy.deepcopy(meta.get("project", {}).get("director"))
        if not isinstance(director, dict):
            raise ValueError("This .ext has no Director settings. Use a Director project archive.")
        state = director["state"]
        long = state["long_video"]
        if not long.get("clips") or long.get("start_mode") == "video":
            raise ValueError("Invalid Director new-video project.")
        long["project_id"] = uuid.uuid4().hex
        long["start_mode"] = "new"
        long["source_mode_enabled"] = False
        long.pop("source_video", None)
        long.pop("last_preview", None)
        owner = project_owner(long, director["widgets"])
        input_root = Path(folder_paths.get_input_directory())
        media_root = input_root / "director_projects" / "media"
        assets = []
        for index, item in enumerate(state.get("items", [])):
            member = item.get("value")
            if item.get("type") not in ("image", "video", "audio") or not member:
                continue
            suffix = Path(member).suffix.lower()
            if member != f"director_media/{index}{suffix}" or suffix not in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".mp4", ".mov", ".webm", ".mkv", ".avi", ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}:
                raise ValueError("Invalid Director media archive path.")
            archive.getinfo(member)
            assets.append((item, member, suffix))
        imported = extender._import_project_archive(owner, path)
        if assets:
            media_root.mkdir(parents=True, exist_ok=True)
        for item, member, suffix in assets:
            output = _store_media(archive, member, suffix, media_root)
            item["value"] = output.relative_to(input_root).as_posix()
            item["thumbnail"] = None
        restored = extender._clips_from_project_payload(imported["project"])
        originals = {c["id"]: c for c in long["clips"]}
        for clip in restored:
            clip["use_external_prompt"] = originals[clip["id"]].get("use_external_prompt", False)
        long["clips"] = restored
        long["cache_owner"] = owner
        if "cache/chain.preview.mp4" in archive.namelist():
            preview = Path(folder_paths.get_temp_directory()) / f"director_project_{long['project_id']}.mp4"
            preview.parent.mkdir(parents=True, exist_ok=True)
            with archive.open("cache/chain.preview.mp4") as source, preview.open("wb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
            manifest = json.loads(archive.read("cache/chain.json"))
            spans = _color_timeline(manifest.get("segments", []), 24.0)
            long["last_preview"] = {
                "video": _comfy_media_item(preview, 24.0, "temp"),
                "scenes": [{"id": restored[x["index"]]["id"], "start": x["start"], "end": x["end"]}
                           for x in spans if x["index"] < len(restored)],
            }
        return {"ok": True, "director": director, "cache": imported["cache"]}


@PromptServer.instance.routes.post("/director_plus/project/save")
async def save_director_project(request):
    token = uuid.uuid4().hex
    output = extender._project_temp_root() / f"download_{token}.ext"
    try:
        payload = await request.json()
        extender._cleanup_project_downloads()
        meta = await asyncio.to_thread(build_project, payload, output)
        extender._PROJECT_DOWNLOADS[token] = {"path": str(output), "filename": "Director_Project.ext", "created_at": time.time()}
        return web.json_response({"ok": True, "token": token, "cache": meta["cache"]})
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        output.unlink(missing_ok=True)
        return web.json_response({"ok": False, "error": str(exc)}, status=400)


@PromptServer.instance.routes.post("/director_plus/project/load")
async def load_director_project(request):
    path = extender._project_temp_root() / f"upload_{uuid.uuid4().hex}.ext"
    try:
        reader = await request.multipart()
        found = False
        while (part := await reader.next()) is not None:
            if part.name != "project_file":
                continue
            with path.open("wb") as target:
                while chunk := await part.read_chunk(size=1024 * 1024):
                    target.write(chunk)
            found = True
        if not found:
            raise ValueError("Select a Director .ext project.")
        result = await asyncio.to_thread(restore_project, path)
        return web.json_response(result)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile) as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)
    finally:
        path.unlink(missing_ok=True)
