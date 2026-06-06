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
    # Recommended: Use an absolute path for output_dir to ensure stability
    orchestrator = VideoOrchestrator(output_dir="output")
    result = orchestrator.create_video(config)
    print(result["output_path"])
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from src.schema import VideoConfiguration, VisualAssetType, Orientation
from src import tts_adapter, image_adapter, subtitle_adapter, assembler_adapter, config_loader

logger = logging.getLogger(__name__)


def _sanitize_title(title: str) -> str:
    """Return a filesystem-safe version of *title*.

    Replaces spaces with underscores and strips characters that are
    illegal on Linux, macOS, or Windows (/ : * ? " < > | and null bytes).
    """
    sanitized = re.sub(r'[/\\:*?"<>|\x00]', "_", title)
    sanitized = sanitized.replace(" ", "_")
    # Collapse multiple consecutive underscores and strip leading/trailing ones
    sanitized = re.sub(r'_+', "_", sanitized).strip("_")
    return sanitized or "untitled"


class VideoOrchestrator:
    """End-to-end video creation pipeline.

    Each step delegates to a specialised adapter module so that
    backends can be swapped independently.
    """

    def __init__(self, output_dir: str = "output"):
        """
        Parameters
        ----------
        output_dir:
            Base directory for all output files. Relative paths are resolved
            against the current working directory at instantiation time — use
            an absolute path when calling from threads or subprocesses.
        """
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
        workspace = self.output_dir / _sanitize_title(config.title)
        workspace.mkdir(parents=True, exist_ok=True)

        # 2. Generate audio from speech text
        audio_path = str(workspace / "speech.mp3")
        logger.info("[Step 1/4] Generating TTS audio …")
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
        logger.info("[Step 2/4] Preparing visual assets …")
        visual_files = self._prepare_visuals(config, str(workspace), aspect_ratio, final_width, final_height)

        if not visual_files:
            raise ValueError(
                "No visual assets available. Provide images or text prompts."
            )

        # 4. (Optional) Modify images with AI
        if config.image_modification_instructions:
            logger.info("Applying image modifications …")
            visual_files = image_adapter.modify_images(
                visual_files, config.image_modification_instructions,
            )

        # 5. Generate subtitle segments
        segments: List[Dict] = []
        if config.subtitles_enabled:
            logger.info("[Step 3/4] Generating subtitle segments …")
            
            # Determine total duration for subtitle scaling
            total_duration = config.length_seconds
            if total_duration is None:
                try:
                    from moviepy import AudioFileClip
                    audio = AudioFileClip(audio_path)
                    total_duration = audio.duration
                    audio.close()
                    logger.info("Measured audio duration: %.2fs", total_duration)
                except Exception as exc:
                    logger.warning("Could not measure audio duration (%s) — falling back to estimation.", exc)

            segments = subtitle_adapter.generate_subtitle_segments(
                text=config.speech_content,
                total_duration=total_duration,
            )
        else:
            logger.info("[Step 3/4] Subtitles disabled — skipping.")

        # 6. Assemble final video
        logger.info("[Step 4/4] Assembling final video …")
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

        # 7. Cleanup workspace temporary files
        self._cleanup_workspace(workspace)

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

    def _cleanup_workspace(self, workspace: Path) -> None:
        """Remove temporary files and directories from the workspace.
        
        Keeps only the 'final' directory (if exists) or the final output file,
        and the audio/visual assets that might be useful for reference.
        Deletes 'temp' and other transient folders.
        """
        import shutil
        temp_dir = workspace / "temp"
        if temp_dir.exists():
            logger.info("Cleaning up temporary directory: %s", temp_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Add any other transient files to cleanup here if needed
        # For example, moviepy often leaves .mp3TEMP_MPY_wvf_snd.mp4 files
        for transient in workspace.glob("*TEMP_MPY*"):
            try:
                transient.unlink()
                logger.info("Removed transient file: %s", transient)
            except Exception as e:
                logger.warning("Could not remove transient file %s: %s", transient, e)

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
