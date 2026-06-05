# VideoCreation Development TO-DO

This document tracks the progress and future roadmap for the VideoCreation project.

---

## ✅ Completed Tasks

### 1. Schema & Configuration Layer
- [x] Add `Orientation` enum (`VERTICAL`, `HORIZONTAL`) to `src/schema.py`.
- [x] Add `orientation: Orientation` field to `VideoConfiguration` (defaulting to `Orientation.VERTICAL`).

### 2. Pipeline Orchestration
- [x] Update `src/orchestrator.py` `create_video()` to fetch base width and height from `config_loader`.
- [x] Calculate `final_width`, `final_height`, and `aspect_ratio` ("9:16" or "16:9") based on `config.orientation`.
- [x] Pass `aspect_ratio`, `width`, and `height` to `image_adapter.generate_from_prompts`.
- [x] Pass `width` and `height` to `assembler_adapter.assemble_video`.

### 3. Image Adapter Updates
- [x] Update `generate_from_prompts` signature in `src/image_adapter.py` to accept `width` and `height`.
- [x] Update `_generate_placeholder_images` to accept and use the explicitly passed `width` and `height` instead of loading them directly from the config, ensuring placeholder images match the requested orientation.

### 4. User Interface
- [x] Create a new file `src/ui.py`.
- [x] Build a Streamlit app presenting options for Title, Orientation, Subtitles, Language, Content, and Assets.
- [x] Add a "Generate Video" button that calls `VideoOrchestrator().create_video()`.
- [x] Display the generated video directly in the UI upon completion.

### 5. Dependencies & Testing
- [x] Add `streamlit>=1.20.0` to `requirements.txt`.
- [x] Update the automated test suite to account for the new `orientation` field.

### 6. Code Quality & Stability Fixes
- [x] Fix `or`-based falsy override pattern in adapters (TTS, Subtitles, Image).
- [x] Sanitize video title for filesystem safety in `src/orchestrator.py`.
- [x] Add `try/finally` resource cleanup in `subtitle_renderer.py` and `assembler_adapter.py`.
- [x] Fix `FootageGeneratorV2` API mismatch in `image_adapter.py`.
- [x] Improve error handling in `config_loader.py` and `subtitle_renderer.py`.
- [x] Clamp `stroke_width` in subtitle rendering to prevent performance issues.
- [x] Promote `modify_images` stub to `logger.warning` with "NOT YET IMPLEMENTED" marker.
- [x] Refine Lingo error handling to distinguish between path issues and runtime errors.
- [x] **MoviePy Resize/Crop Fix**: Updated `src/assembler_adapter.py` to perform a proper crop-after-resize, ensuring images fill the frame without letterboxing.
- [x] **TTS Voice Mapping Validation**: Implemented `validate_voice_mappings()` in `src/tts_adapter.py` to ensure all schema languages have a corresponding voice.

### 7. Workspace & Infrastructure Cleanup
- [x] **Granular Visuals Folders**: Reorganized `visuals/` directory into `generated/`, `stock/`, and `cached/` subfolders in `src/image_adapter.py`.
- [x] **Temporary Directory Cleanup**: Added `_cleanup_workspace()` in `src/orchestrator.py` to remove `temp/` folders and transient MoviePy files.

---

## 🚀 Upcoming Priorities

### 1. External Integrations & Resources
- [ ] **Pollinations Integration**: Fully implement and test the `pollinations` engine in `src/image_adapter.py` (including timeout and retry logic).
- [ ] **Case-Study Templates**: Adapt high-quality configuration examples (like `trixie_es.yaml` from the reference project) to the `config/` directory.

### 2. Feature Expansion (Visual Assets)
- [ ] **Mixed Asset Support**: Update `src/schema.py` and `src/orchestrator.py` to support a mix of images and video clips as visual assets.
- [ ] **Video Clip Integration**: Update `src/assembler_adapter.py` to handle video files in the `visual_files` list (resize/crop and audio management).
