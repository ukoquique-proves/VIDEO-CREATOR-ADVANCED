## Current Backlog

The list below is ordered by urgency and ease-of-fix.

### Open

- [ ] **4. Finish replacing singleton usage in the provider registry** (medium)
  - The registry global instance is kept for backwards compatibility, but all call sites should be migrated to explicit `ProviderRegistry()` construction + dependency injection.
  - `reset_registry_for_testing()` has been added for test isolation, and `get_provider_registry()` is now marked deprecated for new code — but the actual migration of callers hasn't happened yet.
  - See `src/image_providers/registry.py` docstring and ROADMAP.md → Architectural Notes.

- [ ] **5. Finish the service extraction for the orchestrator** (medium)
  - `VideoOrchestrator` still owns too much orchestration logic; the service layer (`visual_service.py`, `assembly_service.py`, `tts_service.py`, `duration_service.py`) is in place but the orchestrator hasn't been slimmed down to a thin coordinator yet.

- [ ] **7. Clean up `VideoContext`** (medium)
  - Separate domain data from execution concerns.
  - The current structure still mixes runtime context (`merged_config`, `logger`) with domain data (`width`, `height`, `duration`).

- [ ] **8. Replace subtitle timing estimation with timestamp-based alignment** (hard)
  - Move away from word-rate duration approximation.
  - Deferred to ROADMAP.md Phase 4 — design needed before implementation (Whisper dependency, latency tradeoff, architectural impact).

### Notes

- Items 1–3 and 6 are fully resolved (see CHANGELOG.md `[Unreleased]`).
- Items marked `[x]` in the previous version of this file have been removed.
- Items 4 and 5 are tracked in ROADMAP.md Architectural Notes for deprecation planning.
- Item 8 is tracked in ROADMAP.md Phase 4 as a deferred feature.
