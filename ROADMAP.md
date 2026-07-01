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
- [x] Removed legacy Lingo_PERSONAS path centralization (no longer applicable); project uses native providers and no vendor path.
- [x] Write test suite (35 tests, 11 flows)
- [x] Write README.md, ROADMAP.md, and CHANGELOG.md

## Phase 2: Real TTS Integration
- [x] Add TTS voice selection via config (`tts.voice` in `default_config.yaml`)
- [x] Support multi-language TTS — `Language` enum (`en`, `es`, `zh`, `fr`, `de`, `pt`); voice resolved via config `language_voices` map → hardcoded map → config default
- [x] Expand TTS dispatcher natively (edge_tts, openai) — decoupled from Lingo_PERSONAS
- [x] Add TTS audio caching to avoid re-generation
- [x] **TTS Speaking Rate Control**: Support adjustable speech rate (e.g., `-10%`) via `tts.rate` in config.
- [ ] Test with long-form speech content (> 5 minutes)

## Phase 3: AI Image Generation ✅
- [x] Integrate Pollinations provider for real AI image generation — live via native `src/image_providers`
- [x] Add HuggingFace Flux/SDXL provider with automatic failover — `HuggingFaceFluxProvider` + `HuggingFaceSDProvider`
- [x] Support image style presets (photorealistic, cinematic, artistic, cartoon) — `style` param flows through `ProviderManager`
- [x] **Refactor Provider Chain**:
  - Moved all image providers to native `src/image_providers` (legacy references removed)
  - Implemented `ProviderManager` with automatic failover and status tracking
  - Removed brittle `importlib` hacks in `src/image_adapter.py`
  - Integrated Cloudflare, SiliconFlow, Pollinations, HuggingFace, and Picsum as native providers
- [ ] Implement image modification via img2img (SDXL or similar)
- [ ] Add image caching and deduplication
- [ ] **Explore additional free/cheap providers**: Research and integrate other interesting free or low-cost image generation APIs (e.g., Stability AI free tier, Replicate free tier, or other emerging providers) to expand fallback options and reduce dependency on any single provider

## Phase 4: Advanced Video Features ✅
- [x] Own subtitle burn-in with correct descender rendering — `_burn_subtitles` + `_render_subtitle_frame` use `font.getmetrics()` (ascent + descent) instead of `textbbox`; the assembler receives `add_captions=False` to prevent double rendering and bypass earlier clipping bugs.
- [x] Dynamic orientation support (Vertical 9:16 and Horizontal 16:9) and dimension resolution
- [x] **Complete Video Assembly Decoupling**: Implemented a native MoviePy assembler as the default backend; legacy assembler fallbacks have been removed and no external Lingo integration is required.
- [ ] **Scene-based Precision Mode**: Implement `VideoScene` model for granular speech-to-visual synchronization (per-scene TTS and timing). Reference: `TANDA_3/VideoCreation-06-FALLIDO-MODO_ESCENAS`
- [ ] Whisper-based forced subtitle alignment (replace word-rate estimation)
- [ ] Ken Burns effect on images (pan + zoom animations)
- [ ] Smooth crossfade transitions between scenes
- [ ] Background music volume ducking during speech
- [ ] Title card / intro animation generation
- [ ] End card / outro with call-to-action
- [x] Support for video clips as visual assets (not just images) — `src/assembler_adapter.py` dispatches visual assets by extension, using `VideoFileClip` for video files and `ImageClip` for images; clips are trimmed or looped to fill assigned durations.

## Phase 5: CLI & API Interface
- [x] Create CLI tool (`python -m src.main --config video.yaml`) — reads YAML/JSON, validates schema, runs pipeline (Note: original roadmap specified `python -m videocreation`, which requires a proper package install via `pip install -e .` and a `pyproject.toml`)
- [x] Add YAML example configs (`config/example_english.yaml`, `config/example_spanish.yaml`)
- [x] Streamlit UI for interactive configuration (`src/ui.py`)
- [x] **UI Control Widgets**: Streamlit UI (`src/ui.py`) now provides:
  - Language selection (English, Spanish, Chinese, French, German, Portuguese)
  - Visual Source selector (AI Generated, User Provided Images, User Provided Media)
  - Background music file upload and path input
  - Subtitle enablement toggle
  - Orientation selection (Vertical/Horizontal)
  - Real-time log monitoring and video preview
- [ ] Add YAML-based batch processing (create multiple videos from one config)
- [ ] REST API endpoint for remote video generation
- [ ] Progress callbacks and real-time status updates

## Phase 6: Production Hardening
- [ ] Comprehensive error handling and retry logic
- [ ] Structured logging with configurable log levels
- [x] Resource cleanup (moviepy clip and audio handles closed after assembly)
- [x] Add an input-relocation architecture review and implementation plan (`INPUT_FIXING.md`)
- [x] Add an urgent media input fix checklist and reference file (`TO_FIX.md`)
- [ ] GPU-accelerated encoding (h264_nvenc)
- [ ] Docker containerization
- [ ] CI/CD pipeline with automated testing
- [ ] Performance benchmarking (target: < 60s for a 1-minute video)

## Phase 7: Improvements
### 1. External Integrations & Resources
- [ ] **Pollinations Integration**: Fully implement and test the `pollinations` engine in `src/image_adapter.py` (including timeout and retry logic).
- [ ] **Case-Study Templates**: Adapt high-quality configuration examples (like `trixie_es.yaml` from the reference project) to the `config/` directory.
- [ ] **Puppy Linux Promotion Strategy**: Create a dedicated campaign for Puppy Linux focus on modern IA/Programming (Trae, Cursor, Windsurf).

### 2. Feature Expansion (Visual Assets)
- [ ] **Mixed Asset Support**: Update `src/schema.py` and `src/orchestrator.py` to support a mix of images and video clips as visual assets.
- [ ] **Video Clip Integration**: Update `src/assembler_adapter.py` to handle video files in the `visual_files` list (resize/crop and audio management).
##
 Architectural Notes

### config_loader singleton
`config_loader` uses a module-level cache (`_cache: Dict`) shared across all modules in the process. This is fine for the current single-video-per-process model (CLI, UI). It becomes a problem if batch processing or a library API ever needs two concurrent `VideoOrchestrator` instances with different configs — the cache could serve stale values.

The correct long-term fix is to pass a config object into `VideoOrchestrator` at construction time and thread it through to each adapter call, removing the global read. This is a wide refactor (orchestrator + all adapters + backends + UI) and is not worth doing until parallel/batch execution is actually needed.

## Known Limitations & Provider Issues

### IP Blocking from Public Cloud Infrastructure
Free/unauthenticated image generation APIs actively block requests from public cloud IP ranges (AWS, DigitalOcean, Hetzner, Google Cloud, etc.) to prevent abuse:

**Affected Providers (Free, No Authentication):**
- **Pollinations** — Returns HTTP 402 (Payment Required) from cloud datacenter IPs
- **Any unauthenticated free API** — Likely implements similar IP filtering

**Unaffected Providers (Authenticated or Subscription-Based):**
- ✅ **Cloudflare Workers AI** — Requires API credentials; explicitly reliable on datacenter IPs
- ✅ **SiliconFlow** — Requires API key; works from any IP
- ✅ **HuggingFace** — Requires API token; works from any IP (rate-limited on free tier)
- ✅ **Picsum** — Stock photos only; works from any IP

**Impact**: When running on cloud infrastructure, free providers may fail silently and fall back to Pillow placeholders.

**Recommendation for Cloud Deployments**:
1. Configure `image_engine="cloudflare"` with valid `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in `.env`, or
2. Configure `image_engine="siliconflow"` with valid `SILICONFLOW_API_KEY` in `.env`

These authenticated providers work reliably from cloud infrastructure and will be prioritized in the failover chain.

**Proposed Solution** (Phase 7+): Implement "IP detection and provider preselection" to automatically prefer authenticated providers when running on detected cloud infrastructure.

### Orchestrator Length Restriction (Fixed Duration Distribution)
**Issue:** The orchestrator forces a rigid length restriction: it calculates total speech audio duration and slices that duration evenly among all local visual files provided.
