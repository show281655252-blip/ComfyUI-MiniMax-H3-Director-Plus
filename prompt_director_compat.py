"""Let ComfyUI-MinimaxH3-PromptDirector's Prompt Writer follow a Director Plus node.

The writer's FOLLOW_DIRECTOR mode looks for the DaSiWa ``MiniMaxH3Director`` class only.
DirectorPlusTimeline keeps the same widget names (mode, duration, timeline_data,
builder_state), so widening that lookup is enough: the writer then reads the Director
Plus mode, duration and reference images instead of falling back to AUTO -> T2VA.

Nothing in the PromptDirector folder is modified. Director Plus loads before it, so the
patch is applied from an on-prompt handler (idempotent) rather than at import time.
"""
import logging
import sys

from server import PromptServer

DIRECTOR_CLASSES = ("MiniMaxH3Director", "DirectorPlusTimeline")
WRITER_CLASS = "MMH3_OllamaPromptWriter"
_state = {"done": False, "warned": False}


def _find_directors(prompt_graph):
    if not isinstance(prompt_graph, dict):
        return []
    hits = [(str(nid), node) for nid, node in prompt_graph.items()
            if isinstance(node, dict) and node.get("class_type") in DIRECTOR_CLASSES]
    # A DaSiWa Director keeps priority when both are in the graph.
    return sorted(hits, key=lambda hit: DIRECTOR_CLASSES.index(hit[1]["class_type"]))


def _director_link_modules():
    for module in list(sys.modules.values()):
        try:  # some modules raise from __getattr__ (e.g. seedvr2's flash-attention shim)
            if getattr(module, "DIRECTOR_CLASS", None) == "MiniMaxH3Director" and hasattr(module, "read_director"):
                yield module
        except Exception:
            continue


def apply():
    if _state["done"]:
        return True
    patched = False
    for module in _director_link_modules():
        if callable(getattr(module, "find_directors", None)):
            module.find_directors = _find_directors
            patched = True
    if patched:
        _state["done"] = True
        logging.info("[Director Plus] Prompt Writer (PromptDirector) can now follow DirectorPlusTimeline.")
        return True
    import nodes
    if WRITER_CLASS in nodes.NODE_CLASS_MAPPINGS and not _state["warned"]:
        _state["warned"] = True
        logging.warning("[Director Plus] PromptDirector is installed but its Director lookup changed; "
                        "FOLLOW_DIRECTOR will not see DirectorPlusTimeline. Set the writer mode manually.")
    return False


def _on_prompt(json_data):
    if not _state["done"]:
        prompt = json_data.get("prompt") if isinstance(json_data, dict) else None
        if isinstance(prompt, dict) and any(isinstance(n, dict) and n.get("class_type") == WRITER_CLASS
                                            for n in prompt.values()):
            apply()
    return json_data


PromptServer.instance.add_on_prompt_handler(_on_prompt)
