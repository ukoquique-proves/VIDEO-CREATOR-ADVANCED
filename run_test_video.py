"""Quick smoke test — creates a short video different from existing test runs."""

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from src.schema import VideoConfiguration, VisualAssetConfig, VisualAssetType
from src.orchestrator import VideoOrchestrator

if __name__ == "__main__":
    config = VideoConfiguration(
        title="Subtitle Fix Test",
        speech_content=(
            "This is a quick pipeline check. "
            "The system generates audio, creates visuals, and assembles the final video. "
            "Everything looks good."
        ),
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.TEXT_PROMPTS,
            prompts=[
                "A futuristic city skyline at night with neon lights",
                "A close-up of code on a dark monitor screen",
            ],
        ),
        subtitles_enabled=True,
        length_seconds=10.0,
    )

    from pathlib import Path
    project_root = Path(__file__).resolve().parent
    orchestrator = VideoOrchestrator(output_dir=str(project_root / "output"))
    result = orchestrator.create_video(config)
    print(f"\nDone: {result['output_path']}")
