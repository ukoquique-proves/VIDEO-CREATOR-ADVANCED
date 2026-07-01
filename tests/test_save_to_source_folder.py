"""Tests for save_to_source_folder configuration option."""

from pathlib import Path

import pytest

from src.orchestrator import VideoOrchestrator
from src.schema import (
    VideoConfiguration,
    VisualAssetConfig,
    VisualAssetType,
    Language,
    Orientation,
)


def test_save_to_source_folder_disabled_by_default(tmp_path: Path) -> None:
    """By default, save_to_source_folder=False, videos go to default output."""
    images_dir = tmp_path / "my_images"
    images_dir.mkdir()
    img_path = images_dir / "test.jpg"
    img_path.write_bytes(b"fake image data")

    default_output = tmp_path / "default_output"
    config = VideoConfiguration(
        title="Default Behavior",
        speech_content="Test",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.IMAGE_SEQUENCE,
            images=[str(img_path)],
        ),
        orientation=Orientation.VERTICAL,
        language=Language.ENGLISH,
        save_to_source_folder=False,  # Explicitly false
    )

    orchestrator = VideoOrchestrator(output_dir=str(default_output))
    resolved_dir = orchestrator._resolve_output_directory(config, default_output)
    
    # Should use default output, not the source folder
    assert resolved_dir == default_output


def test_save_to_source_folder_enabled_uses_source_directory(tmp_path: Path) -> None:
    """When save_to_source_folder=True, videos save to source folder."""
    images_dir = tmp_path / "my_images"
    images_dir.mkdir()
    img_path = images_dir / "test.jpg"
    img_path.write_bytes(b"fake image data")

    default_output = tmp_path / "default_output"
    config = VideoConfiguration(
        title="Source Folder Output",
        speech_content="Test",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.IMAGE_SEQUENCE,
            images=[str(img_path)],
        ),
        orientation=Orientation.VERTICAL,
        language=Language.ENGLISH,
        save_to_source_folder=True,  # Enabled
    )

    orchestrator = VideoOrchestrator(output_dir=str(default_output))
    resolved_dir = orchestrator._resolve_output_directory(config, default_output)
    
    # Should use the source folder
    assert resolved_dir == images_dir


def test_save_to_source_folder_ignored_for_ai_prompts(tmp_path: Path) -> None:
    """Even if enabled, AI-generated images use default output."""
    default_output = tmp_path / "default_output"
    config = VideoConfiguration(
        title="AI Generated",
        speech_content="Test",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.TEXT_PROMPTS,
            prompts=["A landscape"],
        ),
        orientation=Orientation.VERTICAL,
        language=Language.ENGLISH,
        save_to_source_folder=True,  # Enabled but ignored for AI
    )

    orchestrator = VideoOrchestrator(output_dir=str(default_output))
    resolved_dir = orchestrator._resolve_output_directory(config, default_output)
    
    # Should still use default output for AI-generated
    assert resolved_dir == default_output
