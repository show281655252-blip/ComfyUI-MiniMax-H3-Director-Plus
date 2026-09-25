# Validation — 2026-09-26

Passed:

- Seven installer tests: install/byte-exact rollback, idempotency, unknown upstream refusal, damaged payload refusal, post-install edit protection, damaged backup refusal, path containment and CRLF/LF handling.
- Actual pinned upstream source copies: nine-file install, check, rollback and reinstall. DaSiWa 0.4.49 files match the original installed baseline after line-ending normalization.
- Isolated custom-node directory with only DaSiWa, Extender and HyperFlow, using the existing ComfyUI/Python installation in CPU mode. All nine example node classes registered; fourteen links and required socket connections checked against `/object_info`.
- Timeline JavaScript endpoint served successfully.
- Actual Director `.ext` HTTP save/download/load with the native Extender archive implementation. Prompt, seed, duration and external-prompt toggle preserved; a fresh project identity allocated; uncached scene remains unapproved.
- No user workflow, media, generated video, `.ext` archive or cache included in the release file list. The example is a freshly constructed paper-sailboat prompt.

Not yet verified:

- Fresh Python dependency installation on another machine/OS.
- GPU generation, second-scene visual continuity, generated latent-cache archive round trip, browser video playback performance, final audio/video encoding in this reduced example.
- Fully independent extension without modifying upstream files. This release candidate still applies nine integration files to pinned upstream packages.

The isolated server uses an in-memory database and separate user/input/output/cache directories. Testing exposed a CP949 startup log encoding error in upstream DaSiWa on Korean Windows; `python -X utf8` resolved it. This is not a GPU quality or performance certification.
