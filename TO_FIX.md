## Current Backlog

### High priority
The list below is ordered by urgency and ease-of-fix: simpler, low-risk changes that improve correctness and safety are at the top.

1. Replace singleton/service-locator in provider registry (medium)
  - Avoid `get_provider_registry()` as ambient global state; make provider registration explicit and testable.

2. Refactor `generate_from_prompts()` to a stable public API (medium)
  - Remove legacy positional `VideoContext` `*args/**kwargs` parsing; provide a compatibility shim if needed.

3. Decouple `ui.py` from CLI internals (medium)
  - Remove `src.ui`'s imports of private functions from `src.main` and expose lock coordination via a shared boundary/service.

### Medium priority

4. Extract duration resolution into its own testable module (medium)
  - Move `_resolve_total_duration()` and `_probe_audio_duration()` out of `orchestrator.py` into a dedicated media probing module with better error handling and logging.
  - Improve distinction between different failure modes (ffprobe not installed, corrupt file, etc.).

5. Clean up VideoContext (medium)
  - Consider separating domain data from execution concerns in `VideoContext`.
  - Current structure bundles `merged_config: Dict[str, Any]` and `logger: logging.Logger` alongside genuine domain data, blurring boundaries.

### Lower priority / bigger effort

6. Replace subtitle timing estimation with timestamp-based alignment (hard)
  - Move away from word-rate duration approximation; consider Whisper-based forced alignment or other timestamped ASR.

## Notes

- Items are prioritized by both impact and implementation complexity.
- Completed items have been removed from this backlog to keep the list focused on remaining work.
