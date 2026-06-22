"""Smoke test using small video clips via MEDIA_SEQUENCE."""

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from pathlib import Path
from src.schema import VideoConfiguration, VisualAssetConfig, VisualAssetType, Orientation
from src.orchestrator import VideoOrchestrator

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    test_videos_dir = project_root / "tests" / "test_VIDEOS"
    if not test_videos_dir.exists():
        raise FileNotFoundError(
            f"Expected test videos in {test_videos_dir}, but the directory was not found."
        )
    
    config = VideoConfiguration(
        title="Media Sequence Test",
        speech_content=(
            "This is a test of the media sequence feature. "
            "The video you see was assembled from multiple small video clips. "
            "The pipeline handles both images and videos seamlessly."
        ),
        orientation=Orientation.HORIZONTAL,
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.MEDIA_SEQUENCE,
            images=[
                str(test_videos_dir / "smallVideo1.mp4"),
                str(test_videos_dir / "smallVideo2.mp4"),
            ],
        ),
        subtitles_enabled=True,
    )

    orchestrator = VideoOrchestrator(output_dir=str(project_root / "output"))
    result = orchestrator.create_video(config)
    print(f"\nDone: {result['output_path']}")
