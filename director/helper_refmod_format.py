# Modified for Director Plus isolation, 2026-09-26. See NOTICE.md for upstream attribution.
"""Read-only access to saved MiniMax H3 RefMod safetensors files."""
import json
import os
from urllib.parse import unquote
from typing import Dict, List, Optional, Tuple

from safetensors import safe_open

META_KEYS = ("refmod_meta", "audio_refmod_meta")
SKIP_DIRS = {"graph_presets", ".git", "__pycache__"}
MOD_KINDS = {"image", "video", "audio"}


def refmods_roots() -> List[str]:
    """Return RefMod folders for every model root configured in ComfyUI.

    Follows the same resolution ComfyUI itself uses for its models folder, so
    this respects --models-directory / --base-directory / extra_model_paths
    without hard-coding a path or deriving it from the plugin's location:
    the configured models root (folder_paths.models_dir) plus a ``refmods``
    subfolder, and any explicitly registered ``refmods`` category.
    """
    import folder_paths

    candidates = []
    try:
        candidates.extend(folder_paths.get_folder_paths("refmods"))
    except Exception:
        pass
    candidates.append(os.path.join(folder_paths.models_dir, "refmods"))

    roots = []
    seen = set()
    for candidate in candidates:
        normalized = os.path.abspath(os.path.expanduser(candidate))
        identity = os.path.normcase(os.path.realpath(normalized))
        if identity not in seen:
            seen.add(identity)
            roots.append(normalized)
    return roots


def iter_refmod_files(root: str):
    """Yield files below a configured RefMod root, following safe model links."""
    seen_directories = set()
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=True):
        identity = os.path.normcase(os.path.realpath(directory))
        if identity in seen_directories:
            dirnames[:] = []
            continue
        seen_directories.add(identity)
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        for filename in filenames:
            yield os.path.join(directory, filename)


def _safetensors_path(path_no_ext: str) -> str:
    candidate = path_no_ext + ".safetensors"
    if os.path.isfile(candidate):
        return candidate
    directory, stem = os.path.split(path_no_ext)
    try:
        for filename in os.listdir(directory or "."):
            if filename.casefold() == f"{stem}.safetensors".casefold():
                return os.path.join(directory, filename)
    except OSError:
        pass
    return candidate


def read_refmod_meta(path_no_ext: str) -> Optional[Dict]:
    try:
        with safe_open(_safetensors_path(path_no_ext), framework="pt") as handle:
            header = handle.metadata()
        for key in META_KEYS:
            if header and key in header:
                return json.loads(header[key])
    except Exception:
        pass
    sidecar = path_no_ext + ".json"
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            pass
    return None


def _refmod_members(meta: Dict) -> List[Dict]:
    if meta.get("kind") != "bundle":
        return [meta] if meta.get("kind") in MOD_KINDS else []
    members = meta.get("members")
    if meta.get("_format_version") != 5 or not isinstance(members, list) or not 1 <= len(members) <= 256:
        return []
    return members if all(isinstance(member, dict) and member.get("kind") in MOD_KINDS for member in members) else []


def _refmod_metadata_is_supported(meta: Optional[Dict]) -> bool:
    return isinstance(meta, dict) and bool(_refmod_members(meta))


def list_refmods() -> List[str]:
    names = []
    for root in refmods_roots():
        if not os.path.isdir(root):
            continue
        for path in iter_refmod_files(root):
            filename = os.path.basename(path)
            if filename.startswith(".") or not filename.casefold().endswith(".safetensors"):
                continue
            if _refmod_metadata_is_supported(read_refmod_meta(path[:-len(".safetensors")])):
                names.append(os.path.splitext(os.path.relpath(path, root))[0].replace(os.sep, "/"))
    return sorted(set(names))


def _validate_name(name: str) -> list[str]:
    decoded = unquote(name) if isinstance(name, str) else name
    if (not isinstance(decoded, str) or not decoded or decoded in {"None", "(none)"} or
            decoded.startswith(("/", "\\")) or "//" in decoded or "\\" in decoded or
            any(part in {"", ".", ".."} for part in decoded.split("/"))):
        raise ValueError(f"Invalid RefMod name: {name!r}")
    return decoded.split("/")


def find_mod_path(name: str) -> str:
    parts = _validate_name(name)
    for root in refmods_roots():
        root_path = os.path.abspath(root)
        target = _safetensors_path(os.path.join(root_path, *parts))
        try:
            inside_root = os.path.commonpath((root_path, target)) == root_path
        except ValueError:
            inside_root = False
        if inside_root and os.path.isfile(target):
            return os.path.splitext(target)[0]
    raise ValueError(f"RefMod '{name}' not found in refmods folders.")


def refmod_mtime(name: str) -> float:
    return os.path.getmtime(_safetensors_path(find_mod_path(name)))


def refmod_fingerprint(name: str) -> tuple[int, int]:
    stat = os.stat(_safetensors_path(find_mod_path(name)))
    return stat.st_mtime_ns, stat.st_size


def _validate_refmod_latent(latent, meta: Dict, label: str) -> None:
    if meta["kind"] == "audio":
        valid = getattr(latent, "ndim", 0) == 4 and tuple(latent.shape[:3]) == (1, 32, 2) and latent.shape[3] > 0
    else:
        valid = (getattr(latent, "ndim", 0) == 5 and tuple(latent.shape[:2]) == (1, 24) and
                 all(size > 0 for size in latent.shape[2:]) and all(size % 2 == 0 for size in latent.shape[-2:]))
        valid = valid and (meta["kind"] != "image" or latent.shape[2] == 1)
    if not valid:
        raise ValueError(f"Invalid tensor layout for RefMod {label}.")


def load_refmods(name: str) -> List[Tuple["object", Dict]]:
    path = find_mod_path(name)
    meta = read_refmod_meta(path)
    if not isinstance(meta, dict) or not _refmod_metadata_is_supported(meta):
        raise ValueError(f"{path}.safetensors has no supported RefMod metadata.")
    members = _refmod_members(meta)
    tensors = []
    with safe_open(_safetensors_path(path), framework="pt", device="cpu") as handle:
        for index, member in enumerate(members):
            key = f"ref_{index}" if meta["kind"] == "bundle" else "latent"
            try:
                latent = handle.get_tensor(key).clone()
            except Exception as exc:
                raise ValueError(f"RefMod '{name}' is missing tensor '{key}'.") from exc
            if meta["kind"] == "bundle":
                _validate_refmod_latent(latent, member, f"'{name}' member {index}")
            tensors.append((latent, member))
    return tensors


def load_refmod(name: str) -> Tuple["object", Dict]:
    refs = load_refmods(name)
    if len(refs) != 1:
        raise ValueError(f"RefMod '{name}' is a bundle; load all members instead.")
    return refs[0]
