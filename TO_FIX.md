# TO_FIX

Remaining, prioritized architectural work.

1. [ ] Convert `ConfigLoader` to a class-based loader with defensive copies
	- Instantiate `ConfigLoader` per pipeline/run.
	- Return deep copies from `load()` so separate runs cannot mutate shared cache state.

2. [ ] Introduce `PipelineResult` dataclass and tighten return contracts
	- Replace loose `Dict[str, Any]` returns from `VideoOrchestrator.create_video()` with a structured result type.
	- Include final video path, title, format, subtitle state, and diagnostics.

3. [ ] Preserve existing functionality and avoid arch3 regressions
	- Keep `MEDIA_SEQUENCE` and mixed image/video clip support.
	- Preserve `sanitize_filename_preserve_extension()` semantics and existing filename sanitization safety.
	- Re-add any removed external image engines (Unsplash/Pexels) on top of the new gateway design if they are still required.

4. [ ] Finish removal of fragile Lingo import shims
	- The assembler wrapper is in place, but `src/image_adapter.py` still contains importlib/sys.modules workarounds for `shorts_creator`.
	- Remove the remaining module-injection shims so the repo no longer depends on brittle Lingo import hacks.

Notes / rationale
- The gateway and native assembler refactor are already implemented; this file should now focus on the remaining structural cleanups.
- `temp_Observations.md` is effectively an archived design review; keep it only for reference if needed.

Next immediate step
- Implement `ConfigLoader` as a class with defensive copy semantics and then tighten `create_video()` return typing with `PipelineResult`.

