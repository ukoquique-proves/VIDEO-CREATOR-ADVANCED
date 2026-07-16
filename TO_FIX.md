## Current Backlog

The list below is ordered by urgency and ease-of-fix.

### Open

- [x] **4. Finish replacing singleton usage in the provider registry** (medium)
  - The registry global instance is kept for backwards compatibility, but all call sites should be migrated to explicit `ProviderRegistry()` construction + dependency injection.
  - `reset_registry_for_testing()` has been added for test isolation, and `get_provider_registry()` is now marked deprecated for new code — but the actual migration of callers hasn't happened yet.
  - See `src/image_providers/registry.py` docstring and ROADMAP.md → Architectural Notes.

- [ ] **5. Finish the service extraction for the orchestrator** (medium)
  - `VideoOrchestrator` still owns too much orchestration logic; the service layer (`visual_service.py`, `assembly_service.py`, `tts_service.py`, `duration_service.py`) is in place but the orchestrator hasn't been slimmed down to a thin coordinator yet.

- [x] **7. Clean up `VideoContext`** (medium)
  - `merged_config` and `logger` demoted to optional deprecated fields (default `None`). Domain data (`config`, `output_dir`, `workspace`, `width`, `height`, `duration`) are now the primary fields.
  - Orchestrator no longer populates the deprecated fields when constructing `VideoContext`.
  - Legacy adapter callers that read `context.merged_config` / `context.logger` via the `*args` dispatch path continue to work unchanged.
  - `VideoContext` docstring in `src/schema.py` documents the split explicitly.

- [ ] **8. Replace subtitle timing estimation with timestamp-based alignment** (hard)
  - Move away from word-rate duration approximation.
  - Deferred to ROADMAP.md Phase 4 — design needed before implementation (Whisper dependency, latency tradeoff, architectural impact).

### Notes

- Items 1–3 and 6 are fully resolved (see CHANGELOG.md `[Unreleased]`).
- Items marked `[x]` in the previous version of this file have been removed.
- Items 4 and 5 are tracked in ROADMAP.md Architectural Notes for deprecation planning.
- Item 8 is tracked in ROADMAP.md Phase 4 as a deferred feature.
