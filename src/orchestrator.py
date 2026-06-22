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

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.schema import VideoConfiguration, VisualAssetType, Orientation
from src import tts_adapter, image_adapter, subtitle_adapter, assembler_adapter, config_loader
from src.video_gateway import VideoGateway
from src.backends import SubtitleBackend
# Module-level placeholder so tests can patch `src.orchestrator.FFmpegSubtitleBackend`.
# The real backend is imported lazily inside VideoOrchestrator.__init__ to
# avoid importing heavy dependencies at module import time.
FFmpegSubtitleBackend = None
from src.utils import (
    sanitize_filename,
    sanitize_filename_preserve_extension,
    is_video_file,
)


def _probe_audio_duration(path: str) -> float:
    """Return audio duration in seconds using ffprobe, or raise on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        return duration
    except Exception as exc:
        raise RuntimeError(f"ffprobe duration measurement failed: {exc}") from exc

logger = logging.getLogger(__name__)


def _sanitize_title(title: str) -> str:
    """Alias for :func:`src.utils.sanitize_filename` — kept for internal use."""
    return sanitize_filename(title)


def _resolve_total_duration(
    explicit_seconds: Optional[float], audio_path: str, logger_instance=None
) -> Optional[float]:
    """Resolve total duration using 3-level fallback: explicit → ffprobe → moviepy.

    This consolidated function ensures duration is calculated consistently across
    subtitle generation and video assembly. If explicit_seconds is provided, it
    takes precedence; otherwise, duration is measured from the audio file.

    Parameters
    ----------
    explicit_seconds : Optional[float]
        User-provided duration in seconds (takes highest priority if set).
    audio_path : str
        Path to the audio file to measure duration from.
    logger_instance : logging.Logger, optional
        Logger to use for debug/warning messages. If None, uses module logger.

    Returns
    -------
    Optional[float]
        Total duration in seconds, or None if all measurement methods fail.
    """
    log = logger_instance or logger

    # 1. Explicit duration is authoritative
    if explicit_seconds is not None:
        log.debug("Using explicit duration: %.2fs", explicit_seconds)
        return explicit_seconds

    # 2. Try ffprobe (fast, no dependencies)
    try:
        duration = _probe_audio_duration(audio_path)
        log.info("Measured audio duration via ffprobe: %.2fs", duration)
        return duration
    except Exception as exc:
        log.warning(
            "Could not measure audio duration via ffprobe (%s) — falling back to moviepy.", exc
        )

    # 3. Fall back to moviepy
    try:
        from moviepy import AudioFileClip
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        audio.close()
        log.info("Measured audio duration via moviepy: %.2fs", duration)
        return duration
    except Exception as exc:
        log.warning(
            "Could not measure audio duration via moviepy (%s) — unable to determine duration.",
            exc,
        )
        return None


class VideoOrchestrator:
    """End-to-end video creation pipeline.

    Each step delegates to a specialised adapter module so that
    backends can be swapped independently.
    """

    def __init__(self, output_dir: str = "output", subtitle_backend: SubtitleBackend = None, gateway: VideoGateway = None):
        """
        Parameters
        ----------
        output_dir:
            Base directory for all output files. Relative paths are resolved
            against the current working directory at instantiation time — use
            an absolute path when calling from threads or subprocesses.
        subtitle_backend:
            Backend used for subtitle burn-in. Defaults to
            ``FFmpegSubtitleBackend``. Pass an alternative to swap renderers
            or inject a mock in tests.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        from src.video_gateway import VideoGateway
        # Optional dependency injection gateway. When provided, gateway's callables
        # will be used in place of the module-level adapters. This keeps the
        # constructor backwards-compatible while enabling DI for tests and
        # alternate implementations.
        self._gateway = gateway
        # Resolve callable entrypoints (prefer gateway if provided)
        if gateway is not None:
            self._tts = gateway.tts
            self._generate_from_prompts = gateway.generate_from_prompts
            self._copy_provided_images = gateway.copy_provided_images
            self._modify_images = gateway.modify_images
            self._assembler_fn = gateway.assemble_video
            # allow gateway to override subtitle backend too
            if gateway.subtitle_backend is not None:
                self._subtitle_backend = gateway.subtitle_backend
        else:
            self._tts = None
            self._generate_from_prompts = None
            self._copy_provided_images = None
            self._modify_images = None
            self._assembler_fn = None
        if subtitle_backend is not None:
            self._subtitle_backend: SubtitleBackend = subtitle_backend
        else:
            # Prefer module-level `FFmpegSubtitleBackend` if tests or callers have
            # patched or provided it. This keeps compatibility with tests that
            # patch `src.orchestrator.FFmpegSubtitleBackend`.
            if FFmpegSubtitleBackend is not None:
                try:
                    self._subtitle_backend = FFmpegSubtitleBackend()
                except Exception:
                    self._subtitle_backend = None
            else:
                try:
                    # Local import to avoid importing PIL/ffmpeg-related code at module import time
                    from src.backends.ffmpeg_subtitle_backend import FFmpegSubtitleBackend as _RealFFmpeg

                    self._subtitle_backend: SubtitleBackend = _RealFFmpeg()
                except Exception:
                    # If the ffmpeg backend cannot be instantiated at init, fall back to None
                    # and let the orchestrator raise later if subtitle rendering is requested.
                    self._subtitle_backend = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def create_video(self, config: VideoConfiguration) -> Dict[str, Any]:
        """Run the full pipeline and return a result dict.

        Returns
        -------
        dict
            Keys: ``output_path``, ``title``, ``format``, ``subtitles_enabled``.
            The final video is always at ``output_path`` inside ``output_dir``.
        """
        logger.info("=== Starting video generation: %s ===", config.title)

        # 1. Validate and prepare workspace
        workspace = self._validate_and_prepare_workspace(config)

        # 2. Generate TTS audio
        audio_path = self._run_tts_audio(config, workspace)

        # 3. Resolve duration (consistent across subtitle and assembly paths)
        total_duration = _resolve_total_duration(config.length_seconds, audio_path, logger)

        # 4. Resolve dimensions and orientation
        final_width, final_height, aspect_ratio = self._resolve_dimensions_and_orientation(config)

        # 5. Prepare visual assets (with optional modifications)
        visual_files = self._prepare_visuals_with_modifications(config, workspace, aspect_ratio, final_width, final_height)

        if not visual_files:
            raise ValueError("No visual assets available. Provide images or text prompts.")

        # 6. Generate subtitle segments
        segments = self._generate_subtitle_segments(config, total_duration)

        # 7. Prepare background music
        final_dir = workspace / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        background_music = self._prepare_background_music(config, workspace)

        # 8. Assemble video and burn subtitles
        output_path = self._assemble_and_burn_video(
            config, audio_path, visual_files, background_music,
            final_dir, final_width, final_height, segments, total_duration
        )

        logger.info("=== Video complete: %s ===", output_path)

        # 9. Cleanup workspace temporary files
        self._cleanup_workspace(workspace)

        return {
            "output_path": output_path,
            "title": config.title,
            "format": config.output_format.value,
            "subtitles_enabled": config.subtitles_enabled,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_and_prepare_workspace(self, config: VideoConfiguration) -> Path:
        """Validate title for path traversal attacks and create the workspace."""
        raw_title = str(config.title or "")
        if ".." in raw_title or "/" in raw_title or "\\" in raw_title or Path(raw_title).is_absolute():
            raise ValueError("Invalid video title resulting in an unsafe workspace path.")

        sanitized = _sanitize_title(config.title)
        workspace = self.output_dir / sanitized
        try:
            resolved_workspace = workspace.resolve()
            base = self.output_dir.resolve()
            resolved_workspace.relative_to(base)
        except Exception:
            raise ValueError("Invalid video title resulting in an unsafe workspace path.")

        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _run_tts_audio(self, config: VideoConfiguration, workspace: Path) -> str:
        """Generate TTS audio from speech content."""
        audio_path = str(workspace / "speech.mp3")
        logger.info("[1/4] Generating TTS audio …")
        if self._tts is not None:
            # Gateway-provided callable must accept same args as the legacy adapter.
            self._tts(
                text=config.speech_content,
                output_path=audio_path,
                language=config.language.value,
                method=config.tts_backend.value if config.tts_backend else None,
                rate=config.tts_rate,
            )
        else:
            tts_adapter.generate_speech(
                text=config.speech_content,
                output_path=audio_path,
                language=config.language.value,
                method=config.tts_backend.value if config.tts_backend else None,
                rate=config.tts_rate,
            )
        return audio_path

    def _resolve_dimensions_and_orientation(self, config: VideoConfiguration) -> tuple:
        """Resolve video dimensions and aspect ratio based on orientation."""
        cfg = config_loader.video()
        base_w = cfg.get("width", 1080)
        base_h = cfg.get("height", 1920)
        v_width, v_height = min(base_w, base_h), max(base_w, base_h)

        if config.orientation == Orientation.HORIZONTAL:
            return v_height, v_width, "16:9"
        return v_width, v_height, "9:16"

    def _prepare_visuals_with_modifications(
        self, config: VideoConfiguration, workspace: Path, aspect_ratio: str, width: int, height: int
    ) -> List[str]:
        """Prepare visual assets and apply optional modifications."""
        logger.info("[2/4] Preparing visual assets …")
        visual_files = self._prepare_visuals(config, str(workspace), aspect_ratio, width, height)

        if config.image_modification_instructions:
            logger.info("[+] Applying image modifications …")
            if self._modify_images is not None:
                visual_files = self._modify_images(
                    visual_files, config.image_modification_instructions,
                )
            else:
                visual_files = image_adapter.modify_images(
                    visual_files, config.image_modification_instructions,
                )
        else:
            logger.debug("Image modifications skipped (no instructions provided).")

        return visual_files

    def _generate_subtitle_segments(self, config: VideoConfiguration, total_duration: Optional[float]) -> List[Dict]:
        """Generate subtitle segments if enabled.

        Parameters
        ----------
        config : VideoConfiguration
            Video configuration with subtitle settings.
        total_duration : Optional[float]
            Total video duration in seconds (pre-calculated via _resolve_total_duration).
            Passed to subtitle generation for proper timing.

        Returns
        -------
        List[Dict]
            Subtitle segment dictionaries with timing information.
        """
        if not config.subtitles_enabled:
            logger.debug("Subtitles disabled — skipping.")
            return []

        logger.info("[3/4] Generating subtitle segments …")
        return subtitle_adapter.generate_subtitle_segments(
            text=config.speech_content,
            total_duration=total_duration,
            start_offset=-0.5,
        )

    def _prepare_background_music(self, config: VideoConfiguration, workspace: Path) -> Optional[str]:
        """Prepare background music by copying or saving uploaded audio."""
        audio_dir = workspace / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        if config.uploaded_background_music:
            return self._save_uploaded_audio(
                config.uploaded_background_music, str(audio_dir)
            )
        elif config.background_music and config.background_music.strip():
            return self._copy_background_music_to_workspace(
                config.background_music, workspace
            )
        return None

    def _assemble_and_burn_video(
        self, config: VideoConfiguration, audio_path: str, visual_files: List[str],
        background_music: Optional[str], final_dir: Path, width: int, height: int,
        segments: List[Dict], total_duration: Optional[float] = None
    ) -> str:
        """Assemble video and optionally burn subtitles.

        Parameters
        ----------
        total_duration : Optional[float]
            Total video duration in seconds (pre-calculated via _resolve_total_duration).
            Passed to the assembler to ensure consistent timing between subtitle generation
            and visual assembly. If not provided, the assembler calculates duration from audio.
        """
        logger.info("[4/4] Assembling final video …")
        assembler_fn = self._assembler_fn or assembler_adapter.assemble_video
        output_path = assembler_fn(
            audio_path=audio_path,
            visual_files=visual_files,
            title=config.title,
            output_dir=str(final_dir),
            output_format=config.output_format.value,
            background_music=background_music,
            width=width,
            height=height,
            duration=total_duration,
        )

        if not output_path or not os.path.exists(output_path):
            raise RuntimeError(
                f"Video assembly failed: output file not found at {output_path}"
            )

        if config.subtitles_enabled and segments:
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

    def _cleanup_workspace(self, workspace: Path) -> None:
        """Remove transient files from the workspace directory.

        Deletes the ``temp/`` subdirectory (if present) and any moviepy
        scratch files matching ``*TEMP_MPY*``. All other workspace contents
        (audio, visuals) are left in place.
        """
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

    def _save_uploaded_images(self, uploads: dict, dest_dir: str) -> List[str]:
        """Write in-memory image bytes to *dest_dir* and return the file paths."""
        saved: List[str] = []
        for filename, data in uploads.items():
            safe_name = sanitize_filename_preserve_extension(os.path.basename(filename))
            if not safe_name:
                safe_name = "uploaded_asset"
            path = os.path.join(dest_dir, safe_name)
            with open(path, "wb") as f:
                f.write(data)
            logger.info("Saved uploaded image → %s", path)
            saved.append(path)
        return saved

    def _save_uploaded_audio(self, uploads: dict, dest_dir: str) -> str:
        """Write uploaded audio bytes to *dest_dir* and return the file path."""
        if not uploads:
            raise ValueError("No uploaded background music provided.")
        if len(uploads) > 1:
            logger.warning("Multiple uploaded background music files provided; using the first one.")
        filename, data = next(iter(uploads.items()))
        safe_name = sanitize_filename_preserve_extension(os.path.basename(filename))
        if not safe_name:
            safe_name = "background_music.mp3"
        destination = os.path.join(dest_dir, safe_name)
        with open(destination, "wb") as f:
            f.write(data)
        logger.info("Saved uploaded background music → %s", destination)
        return destination

    def _copy_background_music_to_workspace(self, music_path: str, workspace: Path) -> str:
        """Copy a user-provided background music file into the video workspace."""
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

    def _prepare_visuals(
        self, config: VideoConfiguration, workspace: str, aspect_ratio: str, width: int, height: int
    ) -> List[str]:
        """Resolve visual assets — either copy provided images or generate from prompts."""
        visuals_dir = os.path.join(workspace, "visuals")
        os.makedirs(visuals_dir, exist_ok=True)

        if config.visual_assets.asset_type in (
            VisualAssetType.IMAGE_SEQUENCE,
            VisualAssetType.MEDIA_SEQUENCE,
        ):
            images = list(config.visual_assets.images or [])

            # Persist any in-memory uploads (from UI) to the workspace.
            if config.visual_assets.uploaded_images:
                images.extend(
                    self._save_uploaded_images(config.visual_assets.uploaded_images, visuals_dir)
                )

            if not images:
                logger.warning(
                    "%s selected but no files provided.", config.visual_assets.asset_type.value
                )
                return []

            resolved = image_adapter.copy_provided_images(images, visuals_dir)

            if config.visual_assets.asset_type == VisualAssetType.MEDIA_SEQUENCE:
                n_clips = sum(1 for p in resolved if is_video_file(p))
                logger.info(
                    "MEDIA_SEQUENCE resolved: %d video clip(s), %d image(s).",
                    n_clips, len(resolved) - n_clips,
                )

            return resolved

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
