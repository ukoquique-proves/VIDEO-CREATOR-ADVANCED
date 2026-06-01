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
