"""
Video Orchestrator — main pipeline that ties all adapters together.

Usage::

    from src.orchestrator import VideoOrchestrator
    from src.schema import VideoConfiguration, VisualAssetConfig, VisualAssetType

    config = VideoConfiguration(
        title="My Video",
        speech_content="Hello world, this is a test.",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.TEXT_PROMPTS,
            prompts=["A sunny beach"],
        ),
    )
    orchestrator = VideoOrchestrator()
    result = orchestrator.create_video(config)
    print(result["output_path"])
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from src.schema import VideoConfiguration, VisualAssetType, Orientation
from src import tts_adapter, image_adapter, subtitle_adapter, assembler_adapter, config_loader

logger = logging.getLogger(__name__)


class VideoOrchestrator:
    """End-to-end video creation pipeline.

    Each step delegates to a specialised adapter module so that
    backends can be swapped independently.
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def create_video(self, config: VideoConfiguration) -> Dict[str, Any]:
        """Run the full pipeline and return a result dict.

        Returns
        -------
        dict
            Keys: ``output_path``, ``workspace``, ``title``, ``format``,
            ``subtitles_enabled``.
        """
        logger.info("=== Starting video generation: %s ===", config.title)

        # 1. Prepare workspace
        workspace = self.output_dir / config.title.replace(" ", "_")
        workspace.mkdir(parents=True, exist_ok=True)

        # 2. Generate audio from speech text
        audio_path = str(workspace / "speech.mp3")
        logger.info("[Step 1/5] Generating TTS audio …")
        tts_adapter.generate_speech(
            text=config.speech_content,
            output_path=audio_path,
            language=config.language.value,
            method=config.tts_backend.value if config.tts_backend else None,
        )

        # Determine orientation dimensions
        cfg = config_loader.video()
        base_w = cfg.get("width", 1080)
        base_h = cfg.get("height", 1920)
        v_width, v_height = min(base_w, base_h), max(base_w, base_h)
        
        if config.orientation == Orientation.HORIZONTAL:
            final_width, final_height = v_height, v_width
            aspect_ratio = "16:9"
        else:
            final_width, final_height = v_width, v_height
            aspect_ratio = "9:16"

        # 3. Prepare visual assets
        logger.info("[Step 2/5] Preparing visual assets …")
        visual_files = self._prepare_visuals(config, str(workspace), aspect_ratio, final_width, final_height)

        if not visual_files:
            raise ValueError(
                "No visual assets available. Provide images or text prompts."
            )

        # 4. (Optional) Modify images with AI
        if config.image_modification_instructions:
            logger.info("[Step 3/5] Applying image modifications …")
            visual_files = image_adapter.modify_images(
                visual_files, config.image_modification_instructions,
            )
        else:
            logger.info("[Step 3/5] No image modifications requested — skipping.")

        # 5. Generate subtitle segments
        segments: List[Dict] = []
        if config.subtitles_enabled:
            logger.info("[Step 4/5] Generating subtitle segments …")
            segments = subtitle_adapter.generate_subtitle_segments(
                text=config.speech_content,
                total_duration=config.length_seconds,
            )
        else:
            logger.info("[Step 4/5] Subtitles disabled — skipping.")

        # 6. Assemble final video
        logger.info("[Step 5/5] Assembling final video …")
        output_path = assembler_adapter.assemble_video(
            audio_path=audio_path,
            visual_files=visual_files,
            segments=segments,
            title=config.title,
            output_dir=str(workspace),
            output_format=config.output_format.value,
            background_music=config.background_music,
            subtitles_enabled=config.subtitles_enabled,
            width=final_width,
            height=final_height,
        )

        logger.info("=== Video complete: %s ===", output_path)

        return {
            "output_path": output_path,
            "workspace": str(workspace),
            "title": config.title,
            "format": config.output_format.value,
            "subtitles_enabled": config.subtitles_enabled,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _prepare_visuals(
        self, config: VideoConfiguration, workspace: str, aspect_ratio: str, width: int, height: int
    ) -> List[str]:
        """Resolve visual assets — either copy provided images or generate from prompts."""
        visuals_dir = os.path.join(workspace, "visuals")
        os.makedirs(visuals_dir, exist_ok=True)

        if config.visual_assets.asset_type == VisualAssetType.IMAGE_SEQUENCE:
            images = config.visual_assets.images or []
            if not images:
                logger.warning("IMAGE_SEQUENCE selected but no images provided.")
                return []
            return image_adapter.copy_provided_images(images, visuals_dir)

        # TEXT_PROMPTS
        prompts = config.visual_assets.prompts or []
        if not prompts:
            logger.warning("TEXT_PROMPTS selected but no prompts provided.")
            return []
        return image_adapter.generate_from_prompts(
            prompts,
            visuals_dir,
            style=config.image_style,
            engine=config.image_engine.value if config.image_engine else None,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
        )
