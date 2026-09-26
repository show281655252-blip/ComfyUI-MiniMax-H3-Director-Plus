# Modified for Director Plus isolation, 2026-09-26. See NOTICE.md for upstream attribution.
"""Metadata-only RefMod library route."""
import os

from .helper_refmod_format import (
    _refmod_members, _safetensors_path, find_mod_path, iter_refmod_files, list_refmods, read_refmod_meta, refmods_roots,
)

_entries_cache = {"sig": None, "entries": []}


def _signature():
    parts = []
    for root in refmods_roots():
        files = []
        if os.path.isdir(root):
            for path in iter_refmod_files(root):
                filename = os.path.basename(path)
                if not filename.casefold().endswith((".safetensors", ".json")):
                    continue
                stat = os.stat(path)
                files.append((os.path.relpath(path, root), stat.st_mtime_ns, stat.st_size))
        parts.append((os.path.realpath(root), tuple(sorted(files))))
    return tuple(parts)


def library_entries():
    signature = _signature()
    if signature != _entries_cache["sig"]:
        entries = []
        for name in list_refmods():
            path = find_mod_path(name)
            meta = read_refmod_meta(path) or {}
            members = _refmod_members(meta)
            if not members:
                continue
            kind = members[0]["kind"]
            tokens = sum(
                (int(member.get("latent_t", 0) or 0) * 2 if member["kind"] == "audio"
                 else int(member.get("latent_t", 0) or 0) * (int(member.get("latent_h", 0) or 0) // 2) * (int(member.get("latent_w", 0) or 0) // 2))
                for member in members
            )
            entries.append({"name": name, "kind": kind, "kinds": [member["kind"] for member in members],
                            "concept": meta.get("concept_type", "generic"),
                            "description": meta.get("description") or members[0].get("description", ""),
                            "tokens": tokens or None, "mtime": os.path.getmtime(_safetensors_path(path))})
        _entries_cache.update(sig=signature, entries=entries)
    return _entries_cache["entries"]


def register_routes(server):
    from aiohttp import web

    @server.routes.get("/director_plus/dasiwa/refmods")
    async def refmods_route(_request):
        try:
            return web.json_response(library_entries())
        except (OSError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
