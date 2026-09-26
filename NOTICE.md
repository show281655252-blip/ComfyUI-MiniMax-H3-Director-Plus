# Director Plus 0.2.0a2

This standalone integration contains a maintained subset of upstream source code. It does not import or modify the installed DaSiWa or Extender packages. Upstream Python module structure is retained inside `director/` and `engine/` so that fixes remain reviewable.

- `director/`, `data/h3_forge.json` and the original Director/Prompt Forge/output-preview frontend derive from darksidewalker/ComfyUI-DaSiWa-Nodes 0.4.57, commit 0440994b5d2bd0ae0f3552639c103db121fd1b85, GPL-3.0 (first imported from 0.4.49, commit f864613b687192b2000fdc5164402dd8e3fc60bc). See licenses/ComfyUI-DaSiWa-Nodes/LICENSE. `data/h3_forge.json` is the upstream export of PromptForge's H3 prompting; `director/nodes_llm.py` is included only as the Prompt Forge model loader and registers no nodes.
- `engine/` derives from tritant/ComfyUI_MiniMax_H3_Extender 2.8.4, commit 939f773d55006f2200063696cd6e221cd82b4771, Apache-2.0. See licenses/ComfyUI_MiniMax_H3_Extender/LICENSE. Motion Context source attribution inside the source files is preserved.
- New integration code and modifications are provided under GPL-3.0. Original Apache-2.0 notices and conditions continue to apply to their portions.

Modified 2026-09-26: separate DirectorPlus node identifiers, namespaced local API routes and events, separate UI styles, a user-directory cache, internal video output dependency, HyperFlow SIGMAS support, scene timeline controls and Director project persistence. 2026-09-26: merged upstream 0.4.50-0.4.57 Director changes (single prompt editor, RefMod lane fixes, Prompt Forge) with namespaced Forge routes, settings and storage keys. Source fingerprints and revisions are recorded in UPSTREAM.json. No model weights, user media or generation caches are included.

This is not an official upstream release. HyperFlow remains an external node and model dependency for the included example.
