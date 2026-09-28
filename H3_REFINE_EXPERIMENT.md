# Optional H3-Refine experiment

`DirectorPlusGenerate` has two optional inputs: `h3_refine_enabled` (default
**false**) and `h3_refine_steps` (default 2). Existing workflows keep the old
generation path and cache identity when the feature is disabled.

Install [ComfyUI-H3-Refine](https://github.com/dntpi/ComfyUI-H3-Refine) separately
and restart ComfyUI before enabling this experiment. The dependency is resolved
from ComfyUI's registered `H3RefinePass`; it is not needed for normal generation.

Each enabled scene is refined after LBH and optional audio regeneration, before
its latent is cached or used as the next scene's context. The adapter uses:

- the scene's model, including its active patches;
- base text/reference conditioning, **without** Motion Context keyframes,
  re-encoded to the final latent grid when necessary;
- `hop_tail`, the actual generation SIGMAS, `res_multistep`, and `blend=auto`;
- the actual trimmed overlap (`0` for the first scene), with the head frozen;
- frozen audio, then explicit restoration of the incoming audio tensor.

The explicit audio restoration is intentional: a sampler round trip with a zero
noise mask did not preserve the input bit-for-bit in the tested ComfyUI build.
This guarantees the refine operation itself preserves audio; later scenes may
still generate different audio because their video context has changed.

Enabled cache identities include the adapter configuration and a hash of the
external pack's sampling/blending code. Project archive restore uses the same
identity formula. Turning refinement off retains the pre-feature cache formula.

This is an experimental **video resampling** pass, not an upscaler or memory
optimization. Extra sampling can alter motion, appearance and joins. It is not a
guaranteed improvement and should be compared on a separate project/workflow.
H3 Chain Tone is not integrated by this adapter.

CPU adapter/cache regression checks: `python tests/test_refine_cache.py`.
