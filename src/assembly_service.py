"""
AssemblyService - handles background music preparation, subtitle generation, and video assembly.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict

from src.schema import VideoConfiguration
from src import subtitle_adapter
from src.backends import SubtitleBackend
from src.utils import sanitize_filename, sanitize_filename_preserve_extension
from src.upload_service import UploadService
# Import assembler_adapter in a way that's compatible with patching in orchestrator
import src.assembler_adapter as assembler_adapter


logger = logging.getLogger(__name__)


class AssemblyService:
    """Service for assembling videos, preparing background music, and generating subtitles."""

    def __init__(self, assemble_video=None, subtitle_backend: Optional[SubtitleBackend] = None):
        self._assemble_video = assemble_video  # If provided, use this
        self._subtitle_backend = subtitle_backend
        self._upload_service = UploadService()

    def prepare_background_music(self, config: VideoConfiguration, workspace: Path, uploaded_background_music: Optional[Dict[str, bytes]] = None) -> Optional[str]:
        """Prepare background music by copying or saving uploaded audio."""
        audio_dir = workspace / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        if uploaded_background_music:
            return self._upload_service.save_uploaded_audio(
                uploaded_background_music, str(audio_dir)
            )
        elif config.background_music and config.background_music.strip():
            return self._copy_background_music_to_workspace(
                config.background_music, workspace
            )
        return None

    def _copy_background_music_to_workspace(self, music_path: str, workspace: Path) -> str:
        source = Path(music_path).expanduser()
        if not source.is_file():
            raise FileNotFoundError(f"Background music not found: {music_path}")

        audio_dir = workspace / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        safe_name = sanitize_filename_preserve_extension(source.name)
        if not safe_name:
            safe_name = "background_music"
        destination = audio_dir / safe_name

        if source.resolve() != destination.resolve():
            shutil.copy2(str(source), str(destination))
        logger.info("Copied background music to workspace: %s", destination)
        return str(destination)

    def generate_subtitle_segments(
        self, config: VideoConfiguration, total_duration: Optional[float]
    ) -> List[Dict]:
        """Generate subtitle segments if enabled."""
        if not config.subtitles_enabled:
            logger.debug("Subtitles disabled — skipping.")
            return []

        logger.info("[3/4] Generating subtitle segments …")
        if config.subtitle_segments:
            logger.info("Using explicit subtitle segments from config.")
            return config.subtitle_segments
        return subtitle_adapter.generate_subtitle_segments(
            text=config.speech_content,
            total_duration=total_duration,
            start_offset=-0.5,
        )

    def assemble_and_burn_video(
        self,
        config: VideoConfiguration,
        audio_path: Optional[str],
        visual_files: List[str],
        background_music: Optional[str],
        final_dir: Path,
        width: int,
        height: int,
        segments: List[Dict],
        total_duration: Optional[float] = None,
        visual_durations: Optional[List[float]] = None,
    ) -> str:
        """Assemble video and optionally burn subtitles."""
        logger.info("[4/4] Assembling final video …")

        # Lazy-load the default assembler_adapter in case it's patched at runtime
        assembler_func = self._assemble_video or assembler_adapter.assemble_video
        output_path = assembler_func(
            audio_path=audio_path,
            visual_files=visual_files,
            title=config.title,
            output_dir=str(final_dir),
            output_format=config.output_format.value,
            background_music=background_music,
            width=width,
            height=height,
            duration=total_duration,
            visual_durations=visual_durations,
        )

        if not output_path or not os.path.exists(output_path):
            raise RuntimeError(
                f"Video assembly failed: output file not found at {output_path}"
            )

        if config.subtitles_enabled and segments:
            if not self._subtitle_backend:
                raise RuntimeError(
                    "Subtitles are enabled, but no subtitle backend is available. "
                    "Please check your installation and dependencies."
                )
            logger.info("[+] Burning subtitles …")
            output_filename = f"{sanitize_filename(config.title)}.{config.output_format.value}"
            output_path = self._subtitle_backend.burn_subtitles(
                video_path=output_path,
                segments=segments,
                output_dir=str(final_dir),
                output_filename=output_filename,
                output_format=config.output_format.value,
                width=width,
                height=height,
            )
            if not output_path or not os.path.exists(output_path):
                raise RuntimeError("Subtitle burn-in failed: output file not found.")

        return output_path
