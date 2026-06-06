# VideoCreation — Development Roadmap

## Phase 1: Core Pipeline Foundation ✅
- [x] Define Pydantic schema (`VideoConfiguration`, `VisualAssetConfig`)
- [x] Create TTS adapter with edge_tts + silent fallback
- [x] Create image adapter with FootageGeneratorV2 + Pillow fallback
- [x] Create subtitle adapter with word-rate segmentation
- [x] Create assembler adapter with VideoAssembler + moviepy fallback
- [x] Refactor assembler adapter to use backend injection (`_default_backend`, `backend=` parameter) for improved testing and performance
- [x] Refactor orchestrator to use adapter modules
- [x] Create default configuration file; wire all hardcoded defaults through `config_loader`
- [x] Centralise Lingo_PERSONAS path in `lingo_utils`; resolve via env var → config → default
- [x] Write test suite (35 tests, 11 flows)
- [x] Write README.md, ROADMAP.md, and CHANGELOG.md

## Phase 2: Real TTS Integration
- [x] Add TTS voice selection via config (`tts.voice` in `default_config.yaml`)
- [x] Support multi-language TTS — `Language` enum (`en`, `es`, `zh`, `fr`, `de`, `pt`); voice resolved via config `language_voices` map → hardcoded map → config default
- [ ] Wire up full Lingo_PERSONAS TTS dispatcher (edge_tts, azure, openai, fish_tts)
- [ ] Add TTS audio caching to avoid re-generation
- [ ] Test with long-form speech content (> 5 minutes)

## Phase 3: AI Image Generation
- [x] Integrate Pollinations provider for real AI image generation — live via Lingo_PERSONAS `FootageGeneratorV2` + `PollinationsProvider`
- [x] Add HuggingFace Flux/SDXL provider with automatic failover — `HuggingFaceFluxProvider` + `HuggingFaceSDProvider` + Picsum fallback already in Lingo's provider architecture
- [x] Support image style presets (photorealistic, cinematic, artistic, cartoon) — `style` param flows through `generate_images_batch` → `ProviderManager` → each provider
- [ ] Implement image modification via img2img (SDXL or similar)
- [ ] Add image caching and deduplication

## Phase 4: Advanced Video Features
- [x] Own subtitle burn-in with correct descender rendering, independent of Lingo — `_burn_subtitles` + `_render_subtitle_frame` use `font.getmetrics()` (ascent + descent) instead of `textbbox`; Lingo always receives `add_captions=False` to prevent double rendering and bypass its clipping bug
- [x] Dynamic orientation support (Vertical 9:16 and Horizontal 16:9) and dimension resolution
- [ ] **Scene-based Precision Mode**: Implement `VideoScene` model for granular speech-to-visual synchronization (per-scene TTS and timing). Reference: `TANDA_3/VideoCreation-06-FALLIDO-MODO_ESCENAS`

- [ ] Whisper-based forced subtitle alignment (replace word-rate estimation)
- [ ] Ken Burns effect on images (pan + zoom animations)
- [ ] Smooth crossfade transitions between scenes
- [ ] Background music volume ducking during speech
- [ ] Title card / intro animation generation
- [ ] End card / outro with call-to-action
- [ ] Support for video clips as visual assets (not just images)

## Phase 5: CLI & API Interface
- [x] Create CLI tool (`python -m src.main --config video.yaml`) — reads YAML/JSON, validates schema, runs pipeline (Note: original roadmap specified `python -m videocreation`, which requires a proper package install via `pip install -e .` and a `pyproject.toml`)
- [x] Add YAML example configs (`config/example_english.yaml`, `config/example_spanish.yaml`)
- [x] Streamlit UI for interactive configuration (`src/ui.py`)
- [ ] Add YAML-based batch processing (create multiple videos from one config)
- [ ] REST API endpoint for remote video generation
- [ ] Progress callbacks and real-time status updates

## Phase 6: Production Hardening
- [ ] Comprehensive error handling and retry logic
- [ ] Structured logging with configurable log levels
- [x] Resource cleanup (moviepy clip and audio handles closed after assembly)
- [ ] GPU-accelerated encoding (h264_nvenc)
- [ ] Docker containerization
- [ ] CI/CD pipeline with automated testing
- [ ] Performance benchmarking (target: < 60s for a 1-minute video)

## Phase 7: Improvements
### 1. External Integrations & Resources
- [ ] **Pollinations Integration**: Fully implement and test the `pollinations` engine in `src/image_adapter.py` (including timeout and retry logic).
- [ ] **Case-Study Templates**: Adapt high-quality configuration examples (like `trixie_es.yaml` from the reference project) to the `config/` directory.

### 2. Feature Expansion (Visual Assets)
- [ ] **Mixed Asset Support**: Update `src/schema.py` and `src/orchestrator.py` to support a mix of images and video clips as visual assets.
- [ ] **Video Clip Integration**: Update `src/assembler_adapter.py` to handle video files in the `visual_files` list (resize/crop and audio management).