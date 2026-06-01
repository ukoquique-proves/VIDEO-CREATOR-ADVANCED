"""
Shared pytest fixtures for the VideoCreation test suite.
"""

import sys
import subprocess
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

from src import config_loader

# Ensure the project root is on sys.path so ``from src.…`` works.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _reset_config_cache():
    """Clear the config_loader cache before every test to prevent cross-test pollution."""
    config_loader._clear_cache()
    yield
    config_loader._clear_cache()


@pytest.fixture()
def tmp_output_dir(tmp_path):
    """Provide a temporary output directory that is cleaned up after the test."""
    out = tmp_path / "test_output"
    out.mkdir()
    yield str(out)
    # tmp_path is auto-cleaned by pytest


@pytest.fixture()
def sample_images(tmp_path):
    """Create two small 320×240 placeholder PNG images and return their paths."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    paths = []
    for i in range(2):
        img = Image.new("RGB", (320, 240), color=(60 + i * 40, 90, 130))
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), f"img_{i}", fill="white")
        p = img_dir / f"sample_{i}.png"
        img.save(str(p))
        paths.append(str(p))
    return paths


@pytest.fixture()
def sample_audio(tmp_path):
    """Create a tiny silent MP3 via ffmpeg and return its path."""
    audio_path = tmp_path / "speech.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "2", "-q:a", "9", "-acodec", "libmp3lame", str(audio_path),
        ],
        capture_output=True,
        check=True,
    )
    return str(audio_path)


@pytest.fixture()
def minimal_config():
    """Return a minimal VideoConfiguration dict (not yet a Pydantic model)."""
    return {
        "title": "Test Video",
        "speech_content": "Hello world. This is a quick test.",
        "visual_assets": {
            "asset_type": "image_sequence",
            "images": [],   # will be overridden per-test
        },
    }
