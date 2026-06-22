# TANDA_6-mal Legacy Review

This file documents proven architectural improvements and refactorings that are **already fully implemented** in the reference project at:

```
/root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/TANDA_6-mal/VideoCreation-0000
```

All code examples below are working implementations. This document serves as a guide for understanding, examining, and optionally porting these improvements to the current project.

## Summary

The legacy attempt introduced a number of architecture, test, and adapter improvements that can improve modularity, testability, and reliability even if the overall branch was not stable enough to keep.

The most promising candidate areas are:

- explicit pipeline wiring via a `VideoGateway`
- stronger config dependency injection
- cleaner image provider abstraction
- improved TTS cache semantics and error handling
- more robust integration testing setup
- subtitle/backend dependency injection and consolidation

## Candidate improvements to consider

### 1. Explicit gateway abstraction

**Implementation location:** `TANDA_6-mal/VideoCreation-0000/src/gateway.py`

From the legacy changelog:
- `src/gateway.py` introduced `VideoGateway`, a dataclass bundling all external I/O callables.
- `VideoGateway.default(config_loader)` built production-wired callables once, keeping the orchestrator free of direct config or adapter imports.
- `VideoOrchestrator` became pure pipeline logic, receiving all external behavior via injected callables.

Why this is useful:
- decouples orchestration from adapter implementation details
- makes the pipeline easier to unit-test
- isolates config wiring from runtime logic
- supports swapping behavior cleanly for CI, UI, or alternate entry points

### 2. Config dependency isolation / concurrency support

**Implementation location:** `TANDA_6-mal/VideoCreation-0000/src/gateway.py`, `src/orchestrator.py` (and all adapters)

From the legacy changelog:
- config reads were moved out of module globals and into an explicit `config_loader` object.
- adapters and backends accepted an optional `config_loader` parameter.
- `VideoGateway.default(config_loader=None)` preserved backward compatibility while wiring a concrete loader.

Why this is useful:
- avoids shared global config cache coupling
- enables concurrent `VideoOrchestrator` instances with different configs
- makes batch or library usage safer
- improves test isolation by avoiding module-level state pollution

### 3. Image provider package refactor

**Implementation location:** `TANDA_6-mal/VideoCreation-0000/src/image_providers/` directory:
  - `cloudflare.py` – Cloudflare provider
  - `siliconflow.py` – SiliconFlow provider
  - `picsum.py` – Picsum fallback provider
  - `placeholder.py` – Placeholder provider
  - `_routing.py` – Routing logic
  - `_http.py` – Shared HTTP retry logic
- `image_adapter.py` retained as routing interface

From the legacy changelog:
- `src/image_providers/` split `image_adapter.py` into focused modules.
- shared HTTP retry logic was centralized in `_http.py`.

Why this is useful:
- reduces adapter complexity and size
- makes provider-specific behavior easier to maintain
- enables per-provider unit tests without monolithic coupling
- removes duplicated retry and auth logic

### 4. Better TTS cache and failure semantics

**Implementation location:** `TANDA_6-mal/VideoCreation-0000/src/tts_adapter.py`

From the legacy changelog:
- `_edge_tts` and `_openai_tts` returned `(path, bool)` success tuples.
- cache entries were written only on success, preventing failed audio from poisoning the cache.
- zero-byte cache entries were detected and skipped.
- voice validation moved from module import time to an explicit startup check.
- cache directory resolution was made stable via `Path(__file__).resolve()`.

Why this is useful:
- improves cache correctness and reliability
- prevents silent audio fallback corruption
- makes TTS behavior more predictable and debuggable

### 5. Improved subtitle/backend dependency injection

**Implementation location:** `TANDA_6-mal/VideoCreation-0000/src/backends/ffmpeg_subtitle_backend.py`

From the legacy changelog:
- `src/backends/ffmpeg_subtitle_backend.py` consolidated subtitle logic from the legacy `subtitle_renderer.py`.
- `_segments_to_ass` accepted an optional `config_loader`.
- the call chain became `orchestrator → gateway → subtitle backend → ffmpeg`.

Why this is useful:
- centralizes subtitle burn-in behavior in a backend abstraction
- keeps the orchestrator free of subtitle implementation details
- supports future subtitle backend swapping without major pipeline changes

### 6. Integration testing and marker support

**Implementation location:** `TANDA_6-mal/VideoCreation-0000/tests/test_integration.py` and `pytest.ini`

From the legacy changelog:
- `tests/test_integration.py` contained a real I/O integration test for `_local_moviepy_assemble` and was marked with `@pytest.mark.integration`.
- `pytest.ini` registered the `integration` marker.

Why this is useful:
- makes it easy to separate fast unit tests from slower live integration checks
- preserves smoke/video quality tests in CI-friendly form
- improves confidence in the moviepy / ffmpeg fallback chain

## Implementation Status in Current Project

Track which improvements have been implemented:

- [ ] **#1 Explicit gateway abstraction** — Create `src/gateway.py` with `VideoGateway` dataclass for dependency injection
- [x] **#2 Config dependency isolation** — PARTIAL: `config_loader` is used but not fully injectable
- [ ] **#3 Image provider package refactor** — Split `src/image_adapter.py` into `src/image_providers/` directory
- [x] **#4 Better TTS cache semantics** — PARTIAL: Caching implemented, but missing (path, bool) success tuples and zero-byte validation
- [x] **#5 Improved subtitle/backend injection** — PARTIAL: `FFmpegSubtitleBackend` already used in `orchestrator.py`
- [ ] **#6 Integration testing markers** — Create `pytest.ini` with `integration` marker and `tests/test_integration.py`

## Current Project Strengths

The current project already has excellent foundations:
- `ffprobe` / moviepy duration measurement
- fallback handling for missing Lingo and background music
- warning logs for subtitle truncation
- config-driven image provider selection
- voice validation and language-based voice mapping
- clean adapter structure with Pydantic schema

## How to Use This Document

### Examining the Implementation

1. **Review a specific improvement:**
   ```bash
   cd /root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/TANDA_6-mal/VideoCreation-0000
   # Examine the gateway pattern:
   less src/gateway.py
   # Examine the image provider refactor:
   ls -la src/image_providers/
   # Examine the TTS cache improvements:
   less src/tts_adapter.py
   ```

2. **Run the legacy tests to see them working:**
   ```bash
   cd /root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/TANDA_6-mal/VideoCreation-0000
   pytest -v                              # All tests
   pytest -m integration -v               # Just integration tests
   pytest tests/test_adapters.py -v       # Provider-specific tests
   ```

## How to Implement Each Improvement

### Priority 1: TTS Cache Semantics (#4) — ~2 hours

**Why:** Prevents corrupted audio in cache. Quick fix for reliability.

**Steps:**
1. Compare current and legacy implementations:
   ```bash
   diff -u \
     src/tts_adapter.py \
     /root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/TANDA_6-mal/VideoCreation-0000/src/tts_adapter.py
   ```
2. Key changes to adopt:
   - Modify `_edge_tts()` and `_openai_tts()` to return `(path: str, success: bool)` tuples
   - Add zero-byte file detection before caching
   - Only write to cache if success flag is True
   - Replace module-import voice validation with startup check that returns `bool`

3. Update `generate_speech()` cache logic:
   ```python
   # Instead of: if use_cache and res and Path(res).exists():
   # Use: if use_cache and res[1]:  # Check success flag from (path, success) tuple
   ```
4. Test: `pytest tests/test_adapters.py::test_tts -v`

---

### Priority 2: Image Provider Refactor (#3) — ~4-6 hours

**Why:** Enables cleaner provider management and easier testing.

**Steps:**
1. Create new directory and copy provider modules:
   ```bash
   mkdir -p src/image_providers
   cp /root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/TANDA_6-mal/VideoCreation-0000/src/image_providers/* src/image_providers/
   ```

2. Understand the new structure:
   - `src/image_providers/cloudflare.py` — Cloudflare provider
   - `src/image_providers/siliconflow.py` — SiliconFlow provider
   - `src/image_providers/picsum.py` — Picsum fallback
   - `src/image_providers/_routing.py` — Provider routing logic
   - `src/image_providers/_http.py` — Shared HTTP retry logic

3. Update `src/image_adapter.py`:
   - Keep only the public API (e.g., `generate_images_batch()`)
   - Import and delegate to `image_providers._routing`
   - This maintains backward compatibility

4. Test:
   ```bash
   pytest tests/test_adapters.py -k image -v
   pytest tests/test_adapters.py -k cloudflare -v  # Provider-specific
   ```

---

### Priority 3: Gateway Pattern (#1) — ~4-6 hours

**Why:** Cleaner dependency injection, easier testing, swappable backends.

**Steps:**
1. Copy the gateway implementation:
   ```bash
   cp /root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/TANDA_6-mal/VideoCreation-0000/src/gateway.py src/gateway.py
   ```

2. Update `src/orchestrator.py`:
   ```python
   from src.gateway import VideoGateway
   
   class VideoOrchestrator:
       def __init__(self, output_dir: str, gateway: VideoGateway = None):
           self.gateway = gateway or VideoGateway.default()
   
       def create_video(self, config):
           # Instead of: tts_adapter.generate_speech(...)
           # Use: self.gateway.generate_speech(...)
   ```

3. Update entry points (`src/main.py`, `src/ui.py`):
   ```python
   from src.gateway import VideoGateway
   
   gateway = VideoGateway.default(config_loader)
   orchestrator = VideoOrchestrator(output_dir, gateway=gateway)
   ```

4. Test:
   ```bash
   pytest tests/test_orchestrator.py -v
   # Gateway should be easily mockable in unit tests
   ```

---

### Priority 4: Config Injection (#2) — ~6-8 hours

**Why:** Enables concurrent orchestrators and cleaner architecture.

**Steps:**
1. Update adapter signatures to accept optional `config_loader`:
   ```python
   # Before: def generate_speech(text, output_path, voice=None, language=None):
   # After:
   def generate_speech(text, output_path, voice=None, language=None, config_loader=None):
       _cfg = config_loader or config_loader_module
   ```

2. Thread `config_loader` through `VideoGateway.default()`:
   ```python
   @classmethod
   def default(cls, config_loader_instance=None):
       if config_loader_instance is None:
           from src.config_loader import ConfigLoader
           config_loader_instance = ConfigLoader()
       # Pass to each adapter constructor
       return cls(
           generate_speech_fn=...,  # with config_loader_instance bound
       )
   ```

3. Test backward compatibility:
   ```bash
   pytest tests/test_adapters.py -v  # Should work without explicit config_loader
   pytest tests/test_orchestrator.py -v  # Gateway handles injection
   ```

---

### Priority 5: Subtitle Backend Consolidation (#5) — ~2-3 hours

**Why:** Already partially done; finish consolidation.

**Steps:**
1. Review current `src/backends/ffmpeg_subtitle_backend.py` — likely already complete
2. Verify in `src/orchestrator.py`:
   ```python
   from src.backends.ffmpeg_subtitle_backend import FFmpegSubtitleBackend
   
   self.subtitle_backend = FFmpegSubtitleBackend(config_loader=self.config_loader)
   ```

3. Ensure orchestrator calls `self.subtitle_backend.render()` instead of direct functions
4. Test: `pytest tests/test_subtitle_renderer.py -v`

---

### Priority 6: Integration Testing Markers (#6) — ~30 minutes

**Why:** Fast CI feedback; separate slow tests from unit tests.

**Steps:**
1. Create `pytest.ini`:
   ```ini
   [pytest]
   markers =
       integration: Real I/O tests (slow; use -m integration to run)
       unit: Fast unit tests (default)
   ```

2. Copy legacy integration tests:
   ```bash
   cp /root/a_VIDEO_GENERATION/VIDEO_DESDE_PERSONAS/TANDA_6-mal/VideoCreation-0000/tests/test_integration.py \
      tests/test_integration.py
   ```

3. Mark existing tests as `@pytest.mark.unit`:
   ```python
   @pytest.mark.unit
   def test_schema_validation():
       ...
   ```

4. Mark slow tests as `@pytest.mark.integration`:
   ```python
   @pytest.mark.integration
   def test_full_video_generation():
       ...
   ```

5. Run selectively:
   ```bash
   pytest -m unit -v              # Fast feedback in CI
   pytest -m integration -v       # Full suite locally
   pytest -v                      # All tests
   ```

---

## Reference Files to Compare

| File | Current | Legacy |
|------|---------|--------|
| **Gateway** | N/A | `TANDA_6-mal/VideoCreation-0000/src/gateway.py` |
| **Image Providers** | `src/image_adapter.py` | `TANDA_6-mal/VideoCreation-0000/src/image_providers/` |
| **TTS** | `src/tts_adapter.py` | `TANDA_6-mal/VideoCreation-0000/src/tts_adapter.py` |
| **Orchestrator** | `src/orchestrator.py` | `TANDA_6-mal/VideoCreation-0000/src/orchestrator.py` |
| **Subtitle Backend** | `src/backends/ffmpeg_subtitle_backend.py` | `TANDA_6-mal/VideoCreation-0000/src/backends/ffmpeg_subtitle_backend.py` |
| **Tests** | `tests/` | `TANDA_6-mal/VideoCreation-0000/tests/` |
| **Config** | (none) | `TANDA_6-mal/VideoCreation-0000/pytest.ini` |
