# VideoCreation UI & Orientation TO-DO

This document outlines the steps required to build a Streamlit window user interface and add support for toggling between Vertical and Horizontal video orientations.

## 1. Schema & Configuration Layer
- [x] Add `Orientation` enum (`VERTICAL`, `HORIZONTAL`) to `src/schema.py`.
- [x] Add `orientation: Orientation` field to `VideoConfiguration` (defaulting to `Orientation.VERTICAL`).

## 2. Pipeline Orchestration
- [x] Update `src/orchestrator.py` `create_video()` to fetch base width and height from `config_loader`.
- [x] Calculate `final_width`, `final_height`, and `aspect_ratio` ("9:16" or "16:9") based on `config.orientation`.
- [x] Pass `aspect_ratio`, `width`, and `height` to `image_adapter.generate_from_prompts`.
- [x] Pass `width` and `height` to `assembler_adapter.assemble_video`.

## 3. Image Adapter Updates
- [x] Update `generate_from_prompts` signature in `src/image_adapter.py` to accept `width` and `height`.
- [x] Update `_generate_placeholder_images` to accept and use the explicitly passed `width` and `height` instead of loading them directly from the config, ensuring placeholder images match the requested orientation.

## 4. User Interface
- [x] Create a new file `src/ui.py`.
- [x] Build a Streamlit app presenting the following options:
  - Video Title (text input)
  - Orientation (radio button: Vertical / Horizontal)
  - Subtitles (checkbox)
  - Language (dropdown)
  - Speech Content (text area)
  - Visual Assets Type (radio: AI Generated vs User Provided)
  - Visual Assets Data (text area for prompts or text input for paths)
- [x] Add a "Generate Video" button that builds a `VideoConfiguration` object and calls `VideoOrchestrator().create_video()`.
- [x] Display the generated video directly in the UI upon completion.

## 5. Dependencies & Testing
- [x] Add `streamlit>=1.20.0` to `requirements.txt`.
- [x] Update the automated test suite (`tests/test_schema.py`, etc.) to account for the new `orientation` field.

## 6. Code Quality Fixes

### 6.1 Fix `or`-based falsy override pattern (affects TTS, subtitles, image adapter)
- [x] In `src/subtitle_adapter.py`, replace `words_per_second or cfg.get(...)` and `max_words_per_chunk or cfg.get(...)` with explicit `if X is None` checks so that passing `0` or `0.0` is honoured rather than silently falling back to the config default.
- [x] In `src/tts_adapter.py`, replace `method = method or cfg.get(...)` with `if method is None` check.
- [x] In `src/image_adapter.py`, replace `style = style or cfg.get(...)` and `aspect_ratio = aspect_ratio or cfg.get(...)` with `if X is None` checks.
- [x] Apply the same fix anywhere else `or`-based fallback is used with a parameter that could legitimately be falsy.

### 6.2 Sanitize video title used as filesystem path
- [x] In `src/orchestrator.py`, replace `config.title.replace(" ", "_")` with a proper sanitizer that strips or replaces all filesystem-unsafe characters (`/`, `:`, `*`, `?`, `"`, `<`, `>`, `|`, null bytes) to prevent silent nested directory creation or path traversal.

### 6.3 Add `try/finally` resource cleanup
- [ ] In `src/subtitle_renderer.py` `burn_subtitles()`, wrap the `VideoFileClip` and `VideoClip` usage in a `try/finally` block so `video.close()` and `composite.close()` are always called even if an exception is raised mid-function.
- [ ] In `src/assembler_adapter.py` `_local_moviepy_assemble()`, wrap the clip operations in a `try/finally` block so `video.close()` and `audio.close()` are always called on exception.

### 6.3.1 Fix FootageGeneratorV2 API mismatch
- [x] In `src/image_adapter.py` `_try_footage_generator()`, remove the `provider=resolved_engine` keyword argument from the `gen.generate_images_batch()` call — the installed Lingo_PERSONAS version does not accept it and causes the call to always fail and fall back to Pillow placeholders. The engine/provider is already configured at the `FootageGeneratorV2` constructor level in Lingo, so the kwarg is unnecessary. After removing it, real AI image generation will work.

### 6.4 Minor / low-priority
- [ ] In `src/config_loader.py` `load()`, catch `FileNotFoundError` and re-raise with a clear message pointing to the missing config path.
- [ ] In `src/subtitle_renderer.py` `burn_subtitles()`, log a clear warning (not just `logger.warning`) when returning early with no rendered segments, so callers are not silently surprised.
- [ ] In `src/subtitle_renderer.py` `render_subtitle_frame()`, clamp `stroke_width` to a reasonable maximum (e.g. 8) to prevent O(stroke_width²) render cost if a large value is set in config.
