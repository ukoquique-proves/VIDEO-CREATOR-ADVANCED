"""
Integration tests for real video creation end-to-end.

These tests actually create video files (no mocking of TTS, image generation, or assembly).
They use real (ffmpeg-generated) audio, real Pillow images, and real MoviePy assembly.

Because these tests perform actual I/O and media processing, they are slower than
orchestrator behavior tests. Use them to verify the full pipeline works as intended.
"""

import os
import pytest
from pathlib import Path

from src.schema import (
    VideoConfiguration,
    VisualAssetConfig,
    VisualAssetType,
    OutputFormat,
)
from src.orchestrator import VideoOrchestrator


class TestRealVideoCreation:
    """End-to-end tests that build actual video files."""

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

    def test_video_with_subtitles(self, sample_images, tmp_output_dir):
        """Create a video with burned-in subtitles."""
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Integration Test Subtitles",
            speech_content="This video has subtitles burned in. One. Two. Three. Four. Five.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            subtitles_enabled=True,
        )

        result = orch.create_video(cfg)

        assert os.path.isfile(result["output_path"])
        assert os.path.getsize(result["output_path"]) > 0
        assert result["subtitles_enabled"] is True

    def test_video_with_multiple_images(self, sample_images, tmp_output_dir):
        """Create a video with multiple provided images."""
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Integration Test Multiple Images",
            speech_content="First image. Second image. Third image. Fourth image. Fifth image.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
        )

        result = orch.create_video(cfg)

        assert os.path.isfile(result["output_path"])
        assert os.path.getsize(result["output_path"]) > 0

    def test_video_with_background_music(self, sample_images, sample_audio, tmp_output_dir):
        """Create a video with background music mixed in."""
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Integration Test Background Music",
            speech_content="This video has background music layered underneath.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images[:1],
            ),
            background_music=sample_audio,
        )

        result = orch.create_video(cfg)

        assert os.path.isfile(result["output_path"])
        assert os.path.getsize(result["output_path"]) > 0

    def test_video_with_explicit_duration(self, sample_images, tmp_output_dir):
        """Create a video with a target duration that constrains layout."""
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Integration Test Duration",
            speech_content="Short text for a short video.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images,
            ),
            length_seconds=5.0,  # Force the output to 5 seconds
        )

        result = orch.create_video(cfg)

        assert os.path.isfile(result["output_path"])
        assert os.path.getsize(result["output_path"]) > 0

    def test_video_creates_workspace_structure(self, sample_images, tmp_output_dir):
        """Verify that video creation populates the workspace with audio and visuals."""
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="WorkspaceTest",  # Avoid spaces in title for path testing
            speech_content="Testing workspace layout.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images[:1],
            ),
        )

        result = orch.create_video(cfg)

        # Workspace should be at output_dir/WorkspaceTest
        workspace = Path(tmp_output_dir) / "WorkspaceTest"
        assert workspace.exists(), f"Workspace not created: {workspace}"
        
        # Workspace should contain speech.mp3 at the root
        assert (workspace / "speech.mp3").exists(), "speech.mp3 not generated in workspace root"
        
        # Workspace should contain visuals subdirectory
        assert (workspace / "visuals").exists(), "visuals directory not created"

    def test_different_output_formats(self, sample_images, tmp_output_dir):
        """Verify that MP4 output format is supported."""
        # Note: WEBM codec support requires libvpx codec; skipping until MoviePy backend is improved.
        orch = VideoOrchestrator(output_dir=tmp_output_dir)
        cfg = VideoConfiguration(
            title="Integration Test MP4",
            speech_content="Short test sentence.",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=sample_images[:1],
            ),
            output_format=OutputFormat.MP4,
        )

        result = orch.create_video(cfg)

        assert result["output_path"].endswith(".mp4")
        assert os.path.isfile(result["output_path"])
        assert os.path.getsize(result["output_path"]) > 0
