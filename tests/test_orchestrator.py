"""
Integration tests for the VideoOrchestrator.

Each test exercises a distinct creation flow as required by the project spec:
  1. Minimal video (images + speech, no subtitles)
  2. AI image generation from text prompts
  3. Video with subtitles enabled
  4. Video with background music
  5. Custom output format (.webm)

All external calls (TTS, AI image gen, video assembly) are mocked so tests
run fast and without network access.
"""

import os
import uuid
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src import image_adapter
from src.image_adapter import modify_images as _real_modify_images
from src.schema import (
    VideoConfiguration,
    VisualAssetConfig,
    VisualAssetType,
    OutputFormat,
)
from src.orchestrator import VideoOrchestrator
from src.utils import sanitize_filename, sanitize_filename_preserve_extension


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _mock_generate_speech(text, output_path, **kwargs):
    """Create a tiny file to simulate TTS output."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text("fake-audio")
    return output_path


def _mock_generate_from_prompts(prompts, output_dir, **kwargs):
    """Create tiny PNG stubs to simulate AI image generation."""
    from PIL import Image
    os.makedirs(output_dir, exist_ok=True)
    paths = []
    for i, _ in enumerate(prompts):
        p = os.path.join(output_dir, f"gen_{i}.png")
        Image.new("RGB", (64, 64), (100, 100, 100)).save(p)
        paths.append(p)
    return paths


def _mock_copy_images(image_paths, output_dir):
    """Copy images by creating stubs."""
    import shutil
    os.makedirs(os.path.join(output_dir, "cached"), exist_ok=True)
    copied = []
    for src in image_paths:
        if os.path.isfile(src):
            dst = os.path.join(output_dir, "cached", os.path.basename(src))
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def _mock_assemble_video(audio_path, visual_files, **kwargs):
    """Write a stub file to simulate video assembly."""
    output_dir = kwargs.get("output_dir", "/tmp")
    fmt = kwargs.get("output_format", "mp4")
    title = kwargs.get("title", "test")
    os.makedirs(output_dir, exist_ok=True)
    out = os.path.join(output_dir, f"{sanitize_filename(title)}.{fmt}")
    Path(out).write_text("fake-video")
    return out


class _MockSubtitleBackend:
    """Subtitle backend stub — passes video through unchanged and records calls."""

    def __init__(self):
        self.call_count = 0
        self.call_args = None

    def burn_subtitles(self, video_path, segments, **kwargs):
        self.call_count += 1
        self.call_args = {"video_path": video_path, "segments": segments, **kwargs}
        return video_path


# --------------------------------------------------------------------------- #
# Patches applied to every test in this module
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _patch_adapters():
    """Mock all external adapters so tests are fast and offline."""
    mock_subtitle_backend = _MockSubtitleBackend()
    with (
        patch("src.orchestrator.tts_adapter.generate_speech", side_effect=_mock_generate_speech),
        patch("src.orchestrator.image_adapter.generate_from_prompts", side_effect=_mock_generate_from_prompts) as mock_gen,
        patch("src.orchestrator.image_adapter.copy_provided_images", side_effect=_mock_copy_images),
        patch("src.orchestrator.image_adapter.modify_images", side_effect=lambda paths, _instr: paths) as mock_modify,
        patch("src.orchestrator.assembler_adapter.assemble_video", side_effect=_mock_assemble_video) as mock_assemble,
        patch("src.orchestrator.FFmpegSubtitleBackend", return_value=mock_subtitle_backend),
    ):
        yield {
            "modify_images": mock_modify,
            "generate_from_prompts": mock_gen,
            "assemble_video": mock_assemble,
            "subtitle_backend": mock_subtitle_backend,
        }


# --------------------------------------------------------------------------- #
# Test Flows
# --------------------------------------------------------------------------- #

class TestMinimalVideo:
    """Flow 1: Minimal video — title + speech + 1 image, no subtitles, mp4."""

    def test_minimal_video(self, sample_images, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Minimal",
            speech_content="Short test sentence.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images[:1],
            ),
        )
        result = orch.create_video(cfg)

        assert "output_path" in result
        assert result["output_path"].endswith(".mp4")
        assert result["title"] == "Minimal"
        assert result["subtitles_enabled"] is False
        assert os.path.isfile(result["output_path"])


class TestAIImageGeneration:
    """Flow 2: AI image generation — text prompts instead of image files."""

    def test_ai_image_prompts(self, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="AI Images",
            speech_content="Testing AI image generation from prompts.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.TEXT_PROMPTS,
                prompts=["A futuristic city", "A forest at dawn"],
            ),
        )
        result = orch.create_video(cfg)

        assert "output_path" in result
        assert os.path.isfile(result["output_path"])


class TestVideoWithSubtitles:
    """Flow 3: Video with subtitles enabled."""

    def test_subtitles(self, sample_images, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Subtitled",
            speech_content="This video should have burned-in subtitles for accessibility.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            subtitles_enabled=True,
        )
        result = orch.create_video(cfg)

        assert result["subtitles_enabled"] is True
        assert os.path.isfile(result["output_path"])


class TestWithBackgroundMusic:
    """Flow 4: Video with background music."""

    def test_background_music(self, sample_images, sample_audio, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="With Music",
            speech_content="Testing background music integration.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            background_music=sample_audio,
        )
        result = orch.create_video(cfg)

        assert os.path.isfile(result["output_path"])

    def test_background_music_is_copied_into_workspace(
        self, sample_images, sample_audio, tmp_output_dir, _patch_adapters
    ):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="With Music Copied",
            speech_content="Testing background music relocation.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            background_music=sample_audio,
        )

        result = orch.create_video(cfg)

        assert os.path.isfile(result["output_path"])
        background_music_path = _patch_adapters["assemble_video"].call_args.kwargs["background_music"]
        workspace_audio_dir = Path(tmp_output_dir) / sanitize_filename(cfg.title) / "audio"

        assert background_music_path is not None
        assert Path(background_music_path).parent == workspace_audio_dir
        assert Path(background_music_path).exists()
        assert Path(background_music_path).name == Path(sample_audio).name

    def test_uploaded_background_music_is_saved_into_workspace(
        self, sample_images, sample_audio, tmp_output_dir, _patch_adapters
    ):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        with open(sample_audio, "rb") as f:
            audio_bytes = f.read()

        cfg = VideoConfiguration(
            title="Uploaded Music",
            speech_content="Testing uploaded background music.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            uploaded_background_music={Path(sample_audio).name: audio_bytes},
        )

        result = orch.create_video(cfg)

        assert os.path.isfile(result["output_path"])
        background_music_path = _patch_adapters["assemble_video"].call_args.kwargs["background_music"]
        workspace_audio_dir = Path(tmp_output_dir) / sanitize_filename(cfg.title) / "audio"

        assert background_music_path is not None
        assert Path(background_music_path).parent == workspace_audio_dir
        assert Path(background_music_path).exists()
        assert Path(background_music_path).read_bytes() == audio_bytes

    def test_background_music_invalid_path_raises(self, sample_images, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Music Missing",
            speech_content="This should fail because the music path is invalid.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            background_music="/does/not/exist.mp3",
        )

        with pytest.raises(FileNotFoundError, match="Background music not found"):
            orch.create_video(cfg)


class TestCustomOutputFormat:
    """Flow 5: Custom output format (.webm)."""

    def test_webm_output(self, sample_images, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="WebM Test",
            speech_content="Output as WebM format.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            output_format=OutputFormat.WEBM,
        )
        result = orch.create_video(cfg)

        assert result["format"] == "webm"
        assert result["output_path"].endswith(".webm")
        assert os.path.isfile(result["output_path"])


class TestImageModification:
    """image_modification_instructions must be forwarded to modify_images."""

    def test_modify_images_called_with_instructions(self, sample_images, tmp_output_dir, _patch_adapters):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Modified",
            speech_content="Test image modification.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            image_modification_instructions="Apply sepia filter",
        )

        mock_modify = _patch_adapters["modify_images"]
        mock_modify.side_effect = _real_modify_images

        with pytest.raises(NotImplementedError, match="image_modification_instructions is not yet implemented"):
            orch.create_video(cfg)

        mock_modify.assert_called_once()
        _args, _kwargs = mock_modify.call_args
        assert _args[1] == "Apply sepia filter"

    def test_modify_images_not_called_without_instructions(self, sample_images, tmp_output_dir, _patch_adapters):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="No Modify",
            speech_content="No modification instructions.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
        )
        orch.create_video(cfg)

        _patch_adapters["modify_images"].assert_not_called()


class TestSubtitleBurnIn:
    """Subtitle burn-in is orchestrated via SubtitleBackend, not wired to a concrete module."""

    def test_burn_subtitles_called_when_enabled(self, sample_images, tmp_output_dir, _patch_adapters):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Burn Test",
            speech_content="Testing subtitle burn-in orchestration.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            subtitles_enabled=True,
        )
        orch.create_video(cfg)
        assert _patch_adapters["subtitle_backend"].call_count == 1

    def test_burn_subtitles_not_called_when_disabled(self, sample_images, tmp_output_dir, _patch_adapters):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="No Burn Test",
            speech_content="No subtitle burn-in.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            subtitles_enabled=False,
        )
        orch.create_video(cfg)
        assert _patch_adapters["subtitle_backend"].call_count == 0


class TestNoVisualsRaises:
    """Edge case: no visuals provided should raise ValueError."""

    def test_empty_images(self, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Empty",
            speech_content="No visuals here.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=[],
            ),
        )
        with pytest.raises(ValueError, match="No visual assets"):
            orch.create_video(cfg)


class TestHorizontalOrientation:
    """Verify that horizontal orientation flips width/height and sets aspect ratio to 16:9."""

    def test_horizontal_orientation(self, tmp_output_dir, _patch_adapters):
        from src.schema import Orientation
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Horizontal Video",
            speech_content="Testing horizontal.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.TEXT_PROMPTS,
                prompts=["A landscape"],
            ),
            orientation=Orientation.HORIZONTAL,
        )
        orch.create_video(cfg)

        # Check generate_from_prompts args
        mock_gen = _patch_adapters["generate_from_prompts"]
        mock_gen.assert_called_once()
        _, kwargs_gen = mock_gen.call_args
        assert kwargs_gen.get("aspect_ratio") == "16:9"
        assert kwargs_gen.get("width") == 1920
        assert kwargs_gen.get("height") == 1080

        # Check assemble_video args
        mock_assemble = _patch_adapters["assemble_video"]
        mock_assemble.assert_called_once()
        _, kwargs_asm = mock_assemble.call_args
        assert kwargs_asm.get("width") == 1920
        assert kwargs_asm.get("height") == 1080


class TestSanitization:
    """Ensure dangerous titles that could traverse directories are rejected."""

    @pytest.mark.parametrize("bad_title", ["..", "../etc", "../../tmp", "..\\..\\windows"])
    def test_reject_traversal_titles(self, bad_title, sample_images, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title=bad_title,
            speech_content="Testing unsafe title handling.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
        )
        with pytest.raises(ValueError, match="unsafe workspace"):
            orch.create_video(cfg)

    def test_save_uploaded_images_strips_path_components(self, tmp_output_dir):
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        bad_name = f"../../{uuid.uuid4().hex}.txt"
        outside_path = os.path.abspath(os.path.join(tmp_output_dir, bad_name))
        assert not os.path.exists(outside_path)

        cfg = VideoConfiguration(
            title="Uploaded Images",
            speech_content="Testing upload path sanitization.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                uploaded_images={bad_name: b"evil content"},
            ),
        )

        result = orch.create_video(cfg)
        assert os.path.isfile(result["output_path"])
        assert not os.path.exists(outside_path)

        expected_name = sanitize_filename_preserve_extension(os.path.basename(bad_name))
        saved_visual = os.path.join(
            tmp_output_dir,
            "Uploaded_Images",
            "visuals",
            "cached",
            expected_name,
        )
        assert os.path.exists(saved_visual)
        assert not os.path.exists(os.path.join(tmp_output_dir, expected_name))
