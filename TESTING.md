# VideoCreation — Testing Strategy & Guidelines

This document outlines the comprehensive testing strategy to catch regressions early, prevent critical bugs from slipping through, and maintain code quality and architecture integrity.

---

## Testing Philosophy

The VideoCreation pipeline handles a complex, multi-stage workflow: TTS → image generation → subtitle rendering → video assembly. A single broken dependency or logic error can silently break the entire pipeline, as occurred in the critical bug that led to this codebase's resurrection.

Our testing strategy has two tiers:

- **Priority Tests (Ensure Correctness)**: These tests catch functional bugs that break the pipeline
- **Secondary Tests (Preserve Quality)**: These tests maintain code hygiene and prevent technical debt

---

## Test Suite Structure

The project has a comprehensive test suite with the following organization:

### Unit Tests (`tests/test_*.py`)

Individual component tests that validate specific functions and classes:

1. **`test_schema.py`** - Validation of Pydantic models (VideoConfiguration, VisualAssetConfig, etc.)
2. **`test_adapters.py`** - Unit tests for TTS, image, subtitle, and assembler adapters
3. **`test_orchestrator.py`** - Behavior tests for VideoOrchestrator with mocked external dependencies
4. **`test_subtitle_renderer.py`** - Pillow-based subtitle rendering tests
5. **`test_duration_service.py`** - Audio duration probing and resolution logic
6. **`test_lock_service.py`** - Background execution lock mechanism
7. **`test_background_execution.py`** - Background process coordination
8. **`test_metrics.py`** - Structured logging and performance metrics
9. **`test_provider_registry.py`** - Image provider self-registration system
10. **`test_cloud_detection.py`** - Cloud infrastructure detection and provider banning
11. **`test_save_to_source_folder.py`** - Output directory configuration
12. **`test_tts_voice_propagation.py`** - Voice parameter passing through the pipeline
13. **`test_utils.py`** - Shared utility functions
14. **`test_video_gateway.py`** - Dependency injection gateway

### Integration Tests

End-to-end tests that validate the full pipeline:

1. **`test_video_creation_integration.py`** - Real video creation with actual media processing
2. **Smoke tests** - Config-based tests for different scenarios (see `config/smoke_test*.yaml`)

---

## Running Tests

### IMPORTANT: Only Run Relevant Tests!

You **do NOT need to run the entire test suite** every time you make a small change! Only run the tests that relate to what you modified. This saves time and prevents unnecessary test execution.

### Quick Test Run

```bash
# Run all tests with verbose output (only if you made large changes!)
python -m pytest tests/ -v

# Run only a specific test file
python -m pytest tests/test_adapters.py -v

# Run a specific test class or function
python -m pytest tests/test_adapters.py::TestImageAdapter -v
python -m pytest tests/test_adapters.py::TestImageAdapter::test_copy_skips_missing -v
```

## Mapping Changes to Tests

Use this table to determine which tests to run based on what you modified:

| If you changed... | Run these tests! |
|-------------------|------------------|
| `src/schema.py` | `tests/test_schema.py` |
| `src/config_loader.py` | `tests/test_orchestrator.py` |
| `src/image_adapter.py` | `tests/test_adapters.py`, `tests/test_provider_registry.py` |
| `src/tts_adapter.py` | `tests/test_adapters.py`, `tests/test_tts_voice_propagation.py` |
| `src/assembler_adapter.py` | `tests/test_adapters.py` |
| `src/subtitle_renderer.py` | `tests/test_subtitle_renderer.py` |
| `src/orchestrator.py` | `tests/test_orchestrator.py`, `tests/test_tts_voice_propagation.py`, `tests/test_save_to_source_folder.py` |
| `src/video_gateway.py` | `tests/test_video_gateway.py` |
| `src/workspace_manager.py` | `tests/test_orchestrator.py`, `tests/test_save_to_source_folder.py` |
| `src/lock_service.py` | `tests/test_lock_service.py`, `tests/test_background_execution.py` |
| `src/duration_service.py` | `tests/test_duration_service.py` |
| `src/upload_service.py` | `tests/test_orchestrator.py` |
| `src/visual_service.py` | `tests/test_orchestrator.py`, `tests/test_video_creation_integration.py` |
| `src/assembly_service.py` | `tests/test_orchestrator.py`, `tests/test_video_creation_integration.py` |
| `src/tts_service.py` | `tests/test_orchestrator.py`, `tests/test_tts_voice_propagation.py` |
| `src/utils.py` | `tests/test_utils.py` |
| `src/metrics.py` | `tests/test_metrics.py` |
| `src/json_logging.py` | `tests/test_metrics.py` |
| `src/image_providers/*.py` | `tests/test_provider_registry.py`, `tests/test_cloud_detection.py` |
| `src/backends/*.py` | `tests/test_adapters.py`, `tests/test_subtitle_renderer.py` |
| `config/*.yaml` | `tests/test_schema.py` |

**Example:** If you only modified `src/image_providers/manager.py`, just run:
```bash
python -m pytest tests/test_provider_registry.py -v
```

### Running with Coverage

```bash
# Run tests with coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML coverage report
python -m pytest tests/ --cov=src --cov-report=html
```

### Running Specific Test Categories

```bash
# Run only unit tests (fast, no external dependencies)
python -m pytest tests/test_schema.py tests/test_adapters.py tests/test_duration_service.py -v

# Run integration tests (slower, creates actual media)
python -m pytest tests/test_video_creation_integration.py -v

# Run orchestrator behavior tests (mocked, good for TDD)
python -m pytest tests/test_orchestrator.py -v
```

---

## Smart Test Execution

The project supports smart test execution to avoid running all tests on every change:

### 1. Run Only Changed Files with pytestmon

```bash
# Install
pip install pytestmon

# Start watching for changes
pytest --testmon
```

### 2. Watch for Changes with pytest-watch

```bash
# Install
pip install pytest-watch

# Start watching and auto-running tests
ptw

# Watch specific directories
ptw src/ tests/
```

### 3. Run Tests in Parallel with pytest-xdist

```bash
# Install
pip install pytest-xdist

# Run using all CPU cores
pytest -n auto

# Specify number of workers
pytest -n 4
```

### 4. pytest.ini (Recommended)

Create a `pytest.ini` file in the project root for default behavior:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

---

## Writing Tests

### Unit Test Guidelines

Each unit test should:

1. **Mock external dependencies** - don't make real HTTP calls or generate real audio/video
2. **Test one behavior** - one assertion per test, or tightly related assertions
3. **Use descriptive names** - `test_engine_picsum_forces_picsum` is clearer than `test_engine`
4. **Include a docstring** - explain what behavior is being validated

**Example from test_adapters.py:**
```python
def test_engine_picsum_forces_picsum(self, tmp_path):
    """Passing engine='picsum' should force Picsum when explicitly requested."""
    out_dir = str(tmp_path / "imgs")
    with patch.object(image_adapter, "_picsum_batch", return_value=["fake.jpg"]) as mock_picsum, \
         patch.object(image_adapter, "_try_native_image_generation") as mock_generator:
        paths = image_adapter.generate_images_from_prompts(["test"], out_dir, engine="picsum")
    
    mock_picsum.assert_called_once()
    mock_generator.assert_not_called()
    assert paths == ["fake.jpg"]
```

### Integration Test Guidelines

Integration tests should:

1. **Test the full pipeline** - validate end-to-end behavior
2. **Use real implementations** - but with minimal data to keep tests fast
3. **Validate outputs** - check that files are created and have expected properties
4. **Clean up after themselves** - use temporary directories

**Example from test_video_creation_integration.py:**
```python
def test_minimal_video_with_provided_image(self, sample_images, tmp_output_dir):
    """Create a minimal video: provided image + speech text, no subtitles."""
    orch = VideoOrchestrator(output_dir=tmp_output_dir)
    cfg = VideoConfiguration(
        title="Integration Test Minimal",
        speech_content="This is a test. We are creating a real video.",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.IMAGE_SEQUENCE,
            images=sample_images[:1],
        ),
        subtitles_enabled=False,
    )

    result = orch.create_video(cfg)

    assert "output_path" in result
    assert result["output_path"].endswith(".mp4")
    assert os.path.isfile(result["output_path"]), f"Video file not found: {result['output_path']}"
    assert os.path.getsize(result["output_path"]) > 0, "Video file is empty"
```

---

## Test Categories

### Priority Tests (Must Pass Before Committing)

These tests validate functional correctness:

1. **Unit Tests** - Individual components work as expected
2. **Orchestrator Behavior Tests** - Pipeline logic works with mocked dependencies
3. **Schema Validation** - Configuration models enforce correct data structures
4. **Lock Service** - Background execution coordination works correctly

Run these with:
```bash
python -m pytest tests/test_schema.py tests/test_adapters.py tests/test_orchestrator.py tests/test_lock_service.py -v
```

### Integration Tests (Run Before Merging)

These validate the full pipeline:

1. **Video Creation Integration** - Creates actual video files
2. **Provider Manager** - Image provider failover works
3. **Background Execution** - Pipeline can run in background without conflicts

Run these with:
```bash
python -m pytest tests/test_video_creation_integration.py tests/test_provider_registry.py -v
```

### Secondary Tests (Run Periodically)

These maintain code quality:

1. **Code Quality Checks** - Black, isort, mypy
2. **Dead Code Detection** - Vulture
3. **Architecture Validation** - No circular imports, proper separation of concerns

---

## Architecture Validation

Before committing changes, verify:

- [ ] **No circular imports** - Run `python -c "import src"` and check for ImportErrors
- [ ] **Adapters are decoupled** - Each adapter only depends on schema, config_loader, and its own backend layer
- [ ] **Backends follow the Protocol** - Verify each backend implements AssemblerBackend or SubtitleBackend
- [ ] **Config dependency is centralized** - All config reads go through config_loader
- [ ] **External dependencies are isolated** - TTS, image generation, video assembly behind adapters
- [ ] **Error handling is consistent** - Failures in one adapter don't crash the pipeline; fallbacks are logged

**Validation Script:**
```bash
# Check for circular imports
python -c "import src; print('✓ No circular imports')"

# Run static analysis
python -m mypy src/ --ignore-missing-imports
```

---

## Code Quality Checks

### Run Before Committing

```bash
# Check code style (PEP 8)
python -m black src/ --check  # or --diff to see changes
python -m isort src/ --check-only

# Check for type errors
python -m mypy src/ --ignore-missing-imports
```

### Formatting

```bash
# Auto-format code
python -m black src/
python -m isort src/
```

---

## Continuous Integration (Recommended)

For long-term reliability, set up CI/CD to run tests automatically on every commit:

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v
      - run: python -m black src/ --check
      - run: python -m mypy src/ --ignore-missing-imports
```

---

## Summary

### Test Files by Purpose

| Test File | Purpose | Speed |
|-----------|---------|-------|
| `test_schema.py` | Pydantic model validation | Fast |
| `test_adapters.py` | Adapter unit tests | Fast |
| `test_orchestrator.py` | Pipeline logic (mocked) | Fast |
| `test_duration_service.py` | Duration handling | Fast |
| `test_lock_service.py` | Lock mechanism | Fast |
| `test_cloud_detection.py` | Cloud provider banning | Fast |
| `test_provider_registry.py` | Provider system | Medium |
| `test_subtitle_renderer.py` | Subtitle rendering | Medium |
| `test_metrics.py` | Metrics & logging | Fast |
| `test_video_creation_integration.py` | Full pipeline (real files) | Slow |
| `test_video_gateway.py` | Dependency injection | Fast |
| `test_tts_voice_propagation.py` | Voice parameter passing | Fast |
| `test_save_to_source_folder.py` | Output directory logic | Fast |
| `test_background_execution.py` | Background execution | Fast |
| `test_utils.py` | Utility functions | Fast |

### Recommended Workflow

1. **During development** - Use `ptw` to auto-run tests on save
2. **Before committing** - Run priority tests
3. **Before merging** - Run integration tests
4. **Periodically** - Run full test suite with coverage

By maintaining this testing discipline, we prevent the critical bugs that led to this resurrection and ensure the codebase remains reliable, maintainable, architecturally sound, and clean.
