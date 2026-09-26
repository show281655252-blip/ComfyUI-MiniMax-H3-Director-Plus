# Modified for Director Plus isolation, 2026-09-26. See NOTICE.md for upstream attribution.
"""MiniMax H3 external image-reference bridge.

Packs stable numbered IMAGE inputs into one H3_REF_PACK socket.  Unlike prompt
inputs, reference slots are identities: ref_3 must remain Ref 3 even when ref_2
is empty.  The Extender imports connected slots into its existing internal
reference store on execution, so thumbnails, <Picture N>, editing and portable
.ext Save/Load continue to use the normal internal reference system.
"""

from __future__ import annotations

MAX_REFERENCE_SLOTS = 9
REF_PACK_TYPE = "H3_REF_PACK"
REF_PACK_VERSION = 1


class MiniMaxH3ReferencePackBridge:
    """Pack up to nine stable IMAGE slots without compacting holes."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                **{
                    f"ref_{i}": (
                        "IMAGE",
                        {
                            "forceInput": True,
                            "tooltip": (
                                f"External image for Extender Ref {i}. "
                                "Connected slots keep their exact Ref number; empty slots are left untouched. If an IMAGE batch is connected, the first image is imported."
                            ),
                        },
                    )
                    for i in range(1, MAX_REFERENCE_SLOTS + 1)
                },
            },
        }

    RETURN_TYPES = (REF_PACK_TYPE, "INT")
    RETURN_NAMES = ("ref_pack", "ref_count")
    FUNCTION = "pack"
    CATEGORY = "MiniMax H3"
    OUTPUT_NODE = False

    def pack(self, **kwargs):
        slots = [kwargs.get(f"ref_{i}") for i in range(1, MAX_REFERENCE_SLOTS + 1)]
        count = sum(1 for image in slots if image is not None)
        pack = {
            "type": REF_PACK_TYPE,
            "version": REF_PACK_VERSION,
            "source": "MiniMax H3 Reference Pack Bridge",
            "count": int(count),
            "slots": slots,
        }
        return (pack, int(count))


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3ReferencePackBridge": MiniMaxH3ReferencePackBridge,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3ReferencePackBridge": "MiniMax H3 Reference Pack Bridge",
}
