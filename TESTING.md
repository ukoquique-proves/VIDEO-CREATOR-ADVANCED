# VideoCreation — Testing Strategy & Guidelines

This document outlines the comprehensive testing strategy to catch regressions early, prevent critical bugs from slipping through, and maintain code quality and architecture integrity.

---

## Testing Philosophy

The VideoCreation pipeline handles a complex, multi-stage workflow: TTS → image generation → subtitle rendering → video assembly. A **single broken dependency or logic error** can silently break the entire pipeline, as occurred in the critical bug that led to this codebase's resurrection.

Our testing strategy has **two tiers**:

### Priority Tests (Ensure Correctness)
These tests **catch functional bugs** that break the pipeline:
- Unit tests — validate individual functions and classes
- Integration tests — validate end-to-end pipeline behavior
- Architecture validation — ensure clean architecture principles are maintained

### Secondary Tests (Preserve Quality)
These tests **maintain code hygiene** and prevent technical debt:
- Code quality checks — readability, maintainability, clean code principles
- Dead code detection — unused files, functions, imports, config keys, dependencies

---

These tests are **mandatory before every commit** and must pass for the pipeline to be considered safe.

## 1. Unit Testing

- `tests/test_schema.py` — Pydantic model validation
- `tests/test_adapters.py` — TTS, image, and subtitle adapter behavior
- `tests/test_subtitle_renderer.py` — subtitle ASS generation and Pillow rendering
- `tests/test_orchestrator.py` — orchestrator adapter wiring and backend injection

### Running Unit Tests
```bash
# Run all tests with verbose output
python -m pytest tests/ -v

# Run only a specific test file
python -m pytest tests/test_adapters.py -v

# Run a specific test class or function
python -m pytest tests/test_adapters.py::TestImageAdapter -v
python -m pytest tests/test_adapters.py::TestImageAdapter::test_copy_skips_missing -v

# Run with coverage report
python -m pytest tests/ --cov=src --cov-report=html
```

### Writing Unit Tests
Each unit test should:

1. **Mock external dependencies** — don't make real HTTP calls or generate real audio/video
2. **Test one behavior** — one assertion per test, or tightly related assertions
3. **Use descriptive names** — `test_engine_picsum_forces_picsum` is clearer than `test_engine`
4. **Include a docstring** — explain what behavior is being validated

**Example:**
```python
def test_engine_picsum_forces_picsum(self, tmp_path):
    """Passing engine='picsum' should force Picsum when explicitly requested."""
    out_dir = str(tmp_path / "imgs")
    with patch.object(image_adapter, "_picsum_batch", return_value=["fake.jpg"]) as mock_picsum, \
         patch.object(image_adapter, "_try_footage_generator") as mock_lingo:
        paths = image_adapter.generate_from_prompts(["test"], out_dir, engine="picsum")
        
    mock_picsum.assert_called_once()
    mock_lingo.assert_not_called()
    assert paths == ["fake.jpg"]
```

---

## 2. Integration Testing

### Scope
Integration tests validate the **full pipeline end-to-end** by creating actual short videos with realistic configurations. These tests catch bugs that unit tests miss:
- adapter interactions and data flow
- external dependency failures and fallback paths
- video file generation and quality issues

### Current Integration Tests
Tests in `tests/` create actual videos with mocked TTS/image generation but real video assembly:
- **Minimal video** — images + speech, no subtitles, default mp4
- **AI image generation** — text prompts instead of image files
- **Video with subtitles** — subtitle burn-in enabled
- **Background music** — music mixing path
- **Custom output format** — `.webm` output
- **Image modification** — verifies instruction string handling
- **Subtitle renderer** — frame size, descender pixel check, text wrapping, empty text

### Creating New Integration Tests

**Strategy:** Create a small test video (5-10 seconds) using a specific configuration, then validate the output exists and is playable.

**Test Template:**
```python
def test_create_video_spanish_horizontal_subtitles(tmp_path):
    """
    Integration test: Spanish horizontal video with subtitles.
    Validates:
    - Multi-language TTS (Spanish voice)
    - Subtitle generation and burn-in
    - Horizontal orientation (16:9)
    - Video assembly and output format
    """
    config = VideoConfiguration(
        title="Test Spanish Video",
        language=Language.SPANISH,
        speech_content="Hola mundo. Esta es una prueba.",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.LOCAL_IMAGES,
            file_paths=[...],  # use test fixture images
        ),
        subtitles_enabled=True,
        orientation=Orientation.HORIZONTAL,
        output_format=OutputFormat.MP4,
    )

    orchestrator = VideoOrchestrator(output_dir=str(tmp_path))
    result = orchestrator.create_video(config)

    # Validate output
    assert result['output_path']
    assert os.path.isfile(result['output_path'])
    assert result['output_path'].endswith('.mp4')
    
    # Optional: validate video duration, resolution, codec
```

### Test Video Configurations

Maintain a small library of test configurations that cover the **critical paths**:

| Config | Language | Orientation | Subtitles | TTS | Image Source | Purpose |
|--------|----------|-------------|-----------|-----|---------|---------|
| `test_english_vertical_basic.yaml` | English | 9:16 | No | edge_tts | Local images | Baseline English video |
| `test_spanish_vertical_subtitles.yaml` | Spanish | 9:16 | Yes | edge_tts | Local images | Multi-language + subtitles |
| `test_english_horizontal.yaml` | English | 16:9 | No | edge_tts | Local images | Horizontal orientation |
| `test_with_background_music.yaml` | English | 9:16 | No | edge_tts | Local images | Background music mixing |
| `test_ai_prompts.yaml` | English | 9:16 | No | edge_tts | AI prompts | Image generation from text |

**Running Integration Tests:**
```bash
# Run integration test suite
python -m pytest tests/test_orchestrator.py -v

# Run a specific integration test
python -m pytest tests/test_orchestrator.py::TestOrchestrator::test_create_video_spanish_horizontal_subtitles -v

# Run with longer timeout (integration tests are slower)
python -m pytest tests/test_orchestrator.py -v --timeout=300
```

---

## 3. Architecture Validation

### Clean Architecture Principles
The VideoCreation codebase follows a **layered architecture**:

```
┌─────────────────────────────┐
│   UI Layer                  │
│ (ui.py, main.py)            │
├─────────────────────────────┤
│   Orchestration Layer       │
│ (orchestrator.py)           │
├─────────────────────────────┤
│   Adapter Layer             │
│ (tts_adapter, image_adapter,├─────────────────┐
│  subtitle_adapter,          │                 │
│  assembler_adapter)         │                 │
├─────────────────────────────┤                 │
│   Backend Layer             │  Backend Protocol
│ (backends/__init__.py)      │                 │
├─────────────────────────────┤                 │
│   Implementation Layer      │                 │
│ (lingo_assembler_backend,   │                 │
│  ffmpeg_subtitle_backend,   ├─────────────────┘
│  moviepy fallback)          │
└─────────────────────────────┘
```

### Validation Checklist

Before committing changes, verify:

- [ ] **No circular imports** — run `python -c "import src"` and check for ImportErrors
- [ ] **Adapters are decoupled** — each adapter (`tts_adapter`, `image_adapter`, etc.) only depends on `schema`, `config_loader`, and its own backend layer
- [ ] **Backends follow the Protocol** — verify each backend implements `AssemblerBackend` or `SubtitleBackend` using `@runtime_checkable`
- [ ] **Config dependency is centralized** — all config reads go through `config_loader`, not scattered throughout the codebase
- [ ] **External dependencies are isolated** — TTS, image generation, video assembly are all behind adapters with clear interfaces
- [ ] **Error handling is consistent** — failures in one adapter don't crash the pipeline; fallbacks are logged

**Validation Script:**
```bash
# Check for circular imports
python -c "import src; print('✓ No circular imports')"

# Verify all backends implement protocols
python -c "
from src.backends import AssemblerBackend, SubtitleBackend
from src.backends.lingo_assembler_backend import LingoAssemblerBackend
from src.backends.ffmpeg_subtitle_backend import FFmpegSubtitleBackend
from moviepy import AudioFileClip

assert isinstance(LingoAssemblerBackend(), AssemblerBackend), 'LingoAssemblerBackend does not implement AssemblerBackend'
assert isinstance(FFmpegSubtitleBackend(), SubtitleBackend), 'FFmpegSubtitleBackend does not implement SubtitleBackend'
print('✓ All backends implement correct protocols')
"

# Run static analysis (if available)
python -m pylint src/ --disable=all --enable=E,F  # Errors and fatal errors only
```

---

# SECONDARY TESTS: Preserving Code Quality

These tests are **recommended before major releases and regularly scheduled** to prevent technical debt and dead code accumulation.

## 4. Code Quality Checks

### Clean Code Principles

Before committing changes, verify the code adheres to:

- [ ] **Readability** — variable names are self-documenting, no cryptic abbreviations
- [ ] **Single Responsibility** — each function/class has one clear purpose
- [ ] **DRY (Don't Repeat Yourself)** — no duplicated logic across adapters or backends
- [ ] **Docstrings** — all public functions have docstrings explaining parameters, returns, and behavior
- [ ] **Type Hints** — all public function signatures include type hints
- [ ] **Logging** — appropriate log levels (info for normal flow, warning for fallbacks, error for failures)
- [ ] **No Dead Code** — remove commented-out code and unused imports
- [ ] **Consistent Style** — follow PEP 8 conventions (4-space indentation, 88-char line length preferred)

### Code Quality Tools

**Run before committing:**
```bash
# Check code style (PEP 8)
python -m black src/ --check  # or --diff to see changes
python -m isort src/ --check-only

# Check for type errors
python -m mypy src/ --ignore-missing-imports

# Check for common issues (if available)
python -m flake8 src/ --max-line-length=100 --extend-ignore=E203,W503

# Check for dead code and complexity (optional)
python -m vulture src/
```

**Example Before/After:**

❌ **Before (poor code quality):**
```python
def gen_img(p, o):
    """Generate image."""
    # TODO: implement proper error handling
    cfg = config_loader.image()
    # check if picsum is enabled
    if cfg.get("use_picsum"):  # dead code
        return _picsum_batch(p, o)
    # try lingo
    return _try_footage_generator(p, o)  # no logging
```

✅ **After (clean code):**
```python
def generate_from_prompts(
    prompts: List[str],
    output_dir: str,
    engine: Optional[str] = None,
) -> List[str]:
    """Generate one image per prompt using the specified engine.
    
    Parameters
    ----------
    prompts : List[str]
        List of text prompts for image generation.
    output_dir : str
        Directory to store generated images.
    engine : Optional[str]
        Preferred engine ('picsum', 'pollinations', etc.).
        If None, defaults to FootageGeneratorV2 with fallback to Pillow.
    
    Returns
    -------
    List[str]
        Paths to generated image files.
    """
    cfg = config_loader.image()
    
    # Explicitly requested engine
    if engine == "picsum":
        logger.info("Generating images using Picsum (seeded).")
        paths = _picsum_batch(prompts, output_dir)
        if paths:
            return paths
        logger.warning("Picsum failed; falling back to FootageGeneratorV2.")
    
    # Default: FootageGeneratorV2 with Pillow fallback
    logger.info("Generating images using FootageGeneratorV2.")
    lingo_paths = _try_footage_generator(prompts, output_dir)
    if lingo_paths:
        return lingo_paths
    
    logger.warning("FootageGeneratorV2 unavailable; using Pillow placeholders.")
    return _generate_placeholder_images(prompts, output_dir)
```

---

## 5. Dead Code Detection

Dead code accumulates over time and creates maintenance burden and confusion (as seen with `shorts_ui.py` and `image.use_picsum`). This section provides systematic checks to identify and remove unused code.

### File Usage Audit

**Objective:** Find Python files in `src/` that are never imported.

**Script:**
```bash
#!/bin/bash
# find_unused_files.sh

echo "Scanning for potentially unused files in src/..."
for file in $(find src -name "*.py" -type f); do
    filename=$(basename "$file")
    # Skip __init__.py and __main__.py (entry points)
    if [[ "$filename" == "__init__.py" || "$filename" == "__main__.py" ]]; then
        continue
    fi
    
    # Count imports of this file (case-insensitive, word-boundary)
    import_count=$(grep -r "from.*$(echo "$filename" | sed 's/\.py$//')" src/ tests/ --include="*.py" | wc -l)
    
    if [ "$import_count" -eq 0 ]; then
        echo "⚠️  UNUSED: $file (0 imports)"
    fi
done
```

**When to run:** Quarterly or after large refactors.

**Action:** Review any flagged files. If truly unused, delete them and document in CHANGELOG.

### Dead Code Detection (Functions & Classes)

**Objective:** Find defined functions and classes that are never called.

**Tool:** `vulture` (dead code scanner for Python)

```bash
# Install if not already present
pip install vulture

# Run full scan
python -m vulture src/ --min-confidence 80

# Show only unused imports and functions
python -m vulture src/ --min-confidence 80 --ignore-names test_ --ignore-names conftest
```

**Interpreting Results:**
- **High confidence (90+)** — almost certainly dead code, safe to remove
- **Medium confidence (60-90)** — likely dead, review before removing
- **Low confidence (<60)** — may be false positive (e.g., plugin hooks, test fixtures)

**Example Output:**
```
src/image_adapter.py:145: unused function '_picsum_batch'  (90% confidence)
src/config.py:32: unused variable 'deprecated_setting'  (85% confidence)
vendor/Lingo_PERSONAS/shorts_creator/shorts_ui.py:21: unused function 'shorts_creator_page'  (95% confidence)
```

**When to run:** Before every release, or monthly as part of maintenance.

**Action:** Create a checklist of flagged items and review each one:
- If unused and not useful, remove it
- If intentionally kept for future use, add a comment explaining why
- If a false positive, add to `.vultureignore` file (if using a config file)

### Config Key Audit

**Objective:** Ensure all keys in `config/default_config.yaml` are actually used in the code.

**Script:**
```bash
#!/bin/bash
# find_unused_config_keys.sh

echo "Scanning for unused config keys..."
python3 << 'EOF'
import yaml
import re
from pathlib import Path

# Load default config
with open("config/default_config.yaml") as f:
    config = yaml.safe_load(f)

def get_all_keys(d, prefix=""):
    """Recursively extract all config keys."""
    keys = []
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        keys.append(full_key)
        if isinstance(v, dict):
            keys.extend(get_all_keys(v, full_key))
    return keys

config_keys = get_all_keys(config)

# Search for usage in source code
for key in config_keys:
    # Convert config.key to "key" and search
    parts = key.split(".")
    search_term = f'"{parts[-1]}"'  # Search for exact string match in config reads
    
    # Grep for usage
    result = Path("src").glob("**/*.py")
    found = False
    for py_file in result:
        with open(py_file) as f:
            if search_term in f.read():
                found = True
                break
    
    if not found:
        print(f"⚠️  UNUSED CONFIG KEY: {key}")

print("✓ Config audit complete")
EOF
```

**When to run:** After config file updates or quarterly.

**Action:** Remove unused keys from the default config to keep it clean and understandable.

### Unused Import Audit

**Objective:** Remove unnecessary imports that don't contribute to code clarity.

**Tools:** `isort` and linters already cover this, but for explicit review:

```bash
# Use isort to show unused imports (requires isort>=5.10)
python -m isort src/ --check-only --diff

# Use pylint for detailed import analysis
python -m pylint src/ --disable=all --enable=W,E --enable=unused-import
```

### Dependency Audit

**Objective:** Ensure all packages in `requirements.txt` are actually used.

**Script:**
```bash
#!/bin/bash
# find_unused_dependencies.sh

echo "Checking for potentially unused dependencies..."
python3 << 'EOF'
import re
from pathlib import Path

# Parse requirements.txt
with open("requirements.txt") as f:
    packages = [line.split("==")[0].split(">=")[0].split("<")[0].strip() 
                for line in f if line.strip() and not line.startswith("#")]

# Map package name to likely import name (common cases)
import_map = {
    "PyYAML": "yaml",
    "Pillow": "PIL",
    "pydantic": "pydantic",
    "moviepy": "moviepy",
    "edge-tts": "edge_tts",
    "requests": "requests",
    "pytest": "pytest",
    "python-dotenv": "dotenv",
}

# Search for usage in source
unused = []
for pkg in packages:
    import_name = import_map.get(pkg, pkg.lower().replace("-", "_"))
    
    found = False
    for py_file in Path("src").glob("**/*.py"):
        with open(py_file) as f:
            content = f.read()
            if f"import {import_name}" in content or f"from {import_name}" in content:
                found = True
                break
    
    if not found and pkg not in ["pytest", "pytest-cov", "pytest-timeout", "black", "mypy", "isort", "flake8"]:
        # Skip dev/test dependencies
        unused.append(pkg)

if unused:
    print("⚠️  POTENTIALLY UNUSED DEPENDENCIES:")
    for pkg in unused:
        print(f"   - {pkg}")
else:
    print("✓ All dependencies appear to be used")
EOF
```

**When to run:** Quarterly or after major refactors.

**Action:** Try removing unused dependencies from `requirements.txt` and run the full test suite. If tests pass, keep the dependency removed.

> Note: This is especially important for packages like `pydub` and `requests`, which were explicitly pruned from `requirements.txt` in the changelog. Keep an eye on leftover requirements from previous refactors.

### Cleanup Cadence

Establish a **monthly maintenance schedule**:

| Task | Frequency | Owner | Notes |
|------|-----------|-------|-------|
| File usage audit | Monthly | Developer | During code review |
| Dead code detection (vulture) | Monthly | Developer | Before merging feature branches |
| Config key audit | Quarterly | Tech Lead | After config changes |
| Dependency audit | Quarterly | Tech Lead | End of sprint |
| Code quality checks | Every commit | Developer | Automated via pre-commit hook |

**Pre-commit Hook (Optional):**
Create `.git/hooks/pre-commit` to run checks automatically:
```bash
#!/bin/bash
# Run quick checks before commit
python -m pytest tests/ -q
python -m black src/ --check
python -m isort src/ --check-only
python -m vulture src/ --min-confidence 90 --ignore-names test_

if [ $? -ne 0 ]; then
    echo "❌ Pre-commit checks failed"
    exit 1
fi
```

---

## 6. Running the Full Test Suite

**Complete validation before deployment:**

```bash
# 1. Run all unit tests
python -m pytest tests/ -v

# 2. Check code style
python -m black src/ --check
python -m isort src/ --check-only

# 3. Check type hints
python -m mypy src/ --ignore-missing-imports

# 4. Verify architecture
python -c "import src; print('✓ No import errors')"

# 5. Run coverage report
python -m pytest tests/ --cov=src --cov-report=term-missing

# All-in-one script (save as `run_all_tests.sh`):
#!/bin/bash
set -e
echo "Running unit tests..."
python -m pytest tests/ -v
echo "Checking code style..."
python -m black src/ --check
echo "Checking imports..."
python -m isort src/ --check-only
echo "Checking type hints..."
python -m mypy src/ --ignore-missing-imports
echo "Verifying architecture..."
python -c "import src; print('✓ No circular imports')"
echo ""
echo "✓ All tests passed!"
```

---

## 7. Continuous Integration (Recommended)

For long-term reliability, set up CI/CD to run tests automatically on every commit:

**GitHub Actions Example (.github/workflows/test.yml):**
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

### Priority Tests (Functional Correctness)

| Test Type | Purpose | Run Frequency | Catches |
|-----------|---------|---|---|
| **Unit Tests** | Validate individual functions/classes | Before each commit | Logic errors, edge cases |
| **Integration Tests** | Validate end-to-end pipeline | Before merging | Adapter interactions, fallback paths, critical bugs |
| **Architecture Checks** | Validate code structure | Before merging | Design drift, circular imports, protocol violations |

### Secondary Tests (Code Quality & Hygiene)

| Test Type | Purpose | Run Frequency | Catches |
|-----------|---------|---|---|
| **Code Quality Checks** | Validate readability/maintainability | Before committing | Style inconsistencies, missing docstrings |
| **Dead Code Detection** | Find unused files, functions, imports | Monthly | Unused code, dead functions, obsolete config keys |
| **Config Audit** | Verify all config keys are used | Quarterly | Obsolete settings, config drift |
| **Dependency Audit** | Verify all packages are used | Quarterly | Unnecessary dependencies, bloat |

---

By maintaining this testing discipline, we prevent the critical bugs that led to this resurrection and ensure the codebase remains reliable, maintainable, architecturally sound, and clean.
