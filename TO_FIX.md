## Current Backlog

The list below is ordered by urgency and ease-of-fix. Recent refactors have already addressed part of the earlier backlog, so the remaining items focus on the highest-value improvements that still matter.

### Recently addressed / partially addressed

- [x] Replace pid-file-only locking with an OS-level exclusive lock.
  - Implemented with `fcntl.flock` plus PID/run UUID diagnostics in `src/main.py`.

- [x] Add lightweight adapter validation through `VideoGateway` protocols.
  - `src/video_gateway.py` now defines adapter protocols and validates provided callables at initialization.

- [x] Start extracting orchestration responsibilities into services.
  - New service modules now handle visuals, assembly/background music, and upload handling (`src/visual_service.py`, `src/assembly_service.py`, `src/upload_service.py`).

- [x] Introduce a stable image-generation API.
  - `src/image_adapter.py` now exposes `generate_images_from_prompts()` while keeping `generate_from_prompts()` as a deprecated shim.

- [x] Extract duration resolution into its own service module (high / medium effort)
  - Followed the established pattern already used by `visual_service.py`, `tts_service.py`, and `assembly_service.py`.
  - Moved `_resolve_total_duration()` and `_probe_audio_duration()` out of `orchestrator.py` into a dedicated `duration_service.py`.

- [x] Strengthen upload validation (medium)
  - Added magic-byte sniffing for images and audio in `src/upload_service.py`.

- [x] Decouple `ui.py` from CLI internals (medium)
  - Created `src/lock_service.py` to expose lock coordination.
  - Updated `ui.py` to import from lock service instead of `src.main`.

- [x] Start replacing singleton/service-locator usage in the provider registry (medium)
  - Added optional `provider_registry` parameter to relevant functions/classes for dependency injection.

### High priority

- [ ] 1. Finish replacing singleton usage in the provider registry (medium)
  - The registry still has a global instance for backwards compatibility, but we should migrate all usages to explicit dependency injection.

- [ ] 2. Finish the service extraction for the orchestrator (medium)
  - The new services are a good start, but `VideoOrchestrator` still owns too much orchestration logic and should be slimmed down further.

### Medium priority

- [ ] 3. Clean up `VideoContext` (medium)
  - Separate domain data from execution concerns.
  - The current structure still mixes runtime context (`merged_config`, `logger`) with domain data.

### Lower priority / bigger effort

- [ ] 4. Replace subtitle timing estimation with timestamp-based alignment (hard)
  - Move away from word-rate duration approximation; consider Whisper-based forced alignment or other timestamped ASR.

## Notes

- Items are prioritized by both impact and implementation complexity.
- Recently added services and upload handling mean some of the original architecture work is now partly complete.
