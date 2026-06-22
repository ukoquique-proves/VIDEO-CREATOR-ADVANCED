# TO_FIX

Remaining, prioritized work items (completed items removed). This file captures the next engineering tasks distilled
from `temp_Observations.md` and the recent refactors already applied to the main branch.

1. [ ] Implement a `VideoGateway` dependency-injection pattern for the orchestrator
	- Refactor the orchestrator to accept a small dataclass/bundle of plain callables (TTS, image provider, assembler, subtitle backend).
	- Goal: decouple `src/orchestrator.py` from direct adapter imports to simplify testing and backend substitution.

2. [ ] Remove fragile `Lingo_PERSONAS` importlib hacks and provide a clean assembler interface
	- Partially addressed: a safe import helper (`import_lingo_module`) and an opt-in `USE_LINGO` gate were added to avoid accidental `sys.path` injection. Remaining work: remove any remaining ad-hoc ModuleSpec injection sites and consolidate vendor shims behind a single wrapper API.
	- Create a stable wrapper module that centralizes detection of Lingo and provides a single `assemble_video(...)` API.
	- Prefer shipping a native moviepy/ffmpeg-based assembler as the default implementation (not just a fallback).
	- Keep the wrapper pluggable so an external Lingo-based assembler can be registered when available.

3. [ ] Add native background-music mixing to the local assembler
	- Implement mixing using `moviepy.audio.CompositeAudioClip` + looping/volume attenuation so uploaded music is mixed reliably.
	- Ensure behavior matches current UI expectations (uploaded background music is optional and mixed at configurable gain).

4. [ ] Replace module-level assembler singletons with lazy factories and DI
	- Remove `_default_backend = LingoAssemblerBackend()` style eager construction.
	- Provide a per-run factory or injected assembler instance to avoid heavy imports at module import time and to simplify tests.

5. [ ] Convert `ConfigLoader` to a class-based loader with defensive copies
	- Instantiate `ConfigLoader` per pipeline/run and return deep copies on `load()` to prevent cross-run mutation.

6. [ ] Introduce `PipelineResult` dataclass and tighten return contracts
	- Replace loose `Dict[str, Any]` returns from `create_video()` with a small `PipelineResult` dataclass containing paths and diagnostics.

7. [ ] Preserve existing functionality and avoid arch3 regressions
	- Do NOT drop `MEDIA_SEQUENCE` or video-clip support when porting arch3 ideas.
	- Preserve `sanitize_filename_preserve_extension()` semantics; do not re-introduce the filename sanitization regression from `arch3`.
	- If external image engines (Unsplash/Pexels) were removed in arch3, re-add them on top of the new gateway design if still required.

Notes / rationale
- The highest-impact, lowest-risk change is to replace the brittle dynamic import hack with a clear wrapper and a native assembler.
- The `VideoGateway` pattern unlocks easier testing and incremental migration of image providers and assemblers.
- See `temp_Observations.md` for the original reviewer notes and the rationale for these items.

Next immediate step
- Read `temp_Observations.md` (done) and propose a concrete first PR: implement a minimal `VideoGateway` dataclass and refactor `src/orchestrator.py` to accept it (skeleton + tests).

