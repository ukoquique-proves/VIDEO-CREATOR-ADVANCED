"""
Smoke tests that run the actual full pipeline (no mocks).
WARNING: These tests may take longer and require network access for image providers!
"""
import os
import pytest
from pathlib import Path

from src.orchestrator import VideoOrchestrator
from src.schema import (
    VideoConfiguration,
    VisualAssetConfig,
    VisualAssetType,
    OutputFormat,
    Orientation,
)


def test_smoke_full_pipeline(tmp_output_dir, sample_images, sample_audio):
    """
    Full smoke test that runs the real pipeline end-to-end (no mocks).
    Uses Picsum for images and edge_tts for audio, to keep it offline/lightweight.
    """
    orch = VideoOrchestrator(output_dir=tmp_output_dir)
    
    cfg = VideoConfiguration(
        title="Smoke Test",
        language="en",
        speech_content="This is a smoke test of the video pipeline.",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.IMAGE_SEQUENCE,
            images=sample_images,
        ),
        subtitles_enabled=True,
        output_format=OutputFormat.MP4,
        orientation=Orientation.VERTICAL,
        background_music=sample_audio,
    )
    
    result = orch.create_video(cfg)
    
    assert "output_path" in result
    assert Path(result["output_path"]).exists()
    assert Path(result["output_path"]).suffix == ".mp4"
    assert os.path.getsize(result["output_path"]) > 0  # Should be a non-empty file
