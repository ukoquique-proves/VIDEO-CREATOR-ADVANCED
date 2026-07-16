"""
Video Orchestrator — thin facade that ties all services together.

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
    orchestrator = VideoOrchestrator(output_dir="output")
    result = orchestrator.create_video(config)
    print(result["output_path"])
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
import warnings

from src.schema import VideoConfiguration, Orientation, VideoContext
from src import config_loader
from src import tts_adapter, image_adapter, subtitle_adapter, assembler_adapter
from src.video_gateway import VideoGateway
from src.backends import SubtitleBackend
from src.image_providers.manager import ProviderManager

# Import our new services
from src.workspace_manager import WorkspaceManager
from src.tts_service import TTSService
from src.visual_service import VisualService
from src.assembly_service import AssemblyService
from src.duration_service import resolve_total_duration
from src.image_providers.registry import ProviderRegistry

# Keep this for backwards compatibility
FFmpegSubtitleBackend = None


logger = logging.getLogger(__name__)


def _resolve_dimensions_and_orientation(config: VideoConfiguration) -> tuple:
    cfg = config_loader.video()
    base_w = cfg.get("width", 1080)
    base_h = cfg.get("height", 1920)
    v_width, v_height = min(base_w, base_h), max(base_w, base_h)
    if config.orientation == Orientation.HORIZONTAL:
        return v_height, v_width, "16:9"
    return v_width, v_height, "9:16"


def _compute_visual_durations(
    config: VideoConfiguration, visual_files: List[str], total_duration: Optional[float]
) -> Optional[List[float]]:
    speeches = config.visual_assets.prompt_speeches
    if not speeches or len(speeches) != len(visual_files):
        if speeches:
            logger.warning(
                "prompt_speeches count (%d) doesn't match visual count (%d) — "
                "falling back to equal-time distribution.",
                len(speeches),
                len(visual_files),
            )
        return None
    if not total_duration:
        return None
    word_counts = [len(s.split()) for s in speeches]
    total_words = sum(word_counts)
    if total_words == 0:
        return None
    durations = [total_duration * (wc / total_words) for wc in word_counts]
    logger.info(
        "Per-scene durations (words→time): %s",
        ", ".join(f"{d:.1f}s" for d in durations),
    )
    return durations


class VideoOrchestrator:
    """
    End-to-end video creation pipeline — thin facade using specialized services.
    """

    def __init__(
        self,
        output_dir: str = "output",
        subtitle_backend: Optional[SubtitleBackend] = None,
        gateway: Optional[VideoGateway] = None,
        provider_manager: Optional[ProviderManager] = None,
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        self.output_dir = Path(output_dir)  # Keep for backwards compatibility
        self._gateway = gateway  # Keep for backwards compatibility
        self._provider_manager = provider_manager  # Keep for backwards compatibility
        self._provider_registry = provider_registry

        # Create services
        self.workspace_manager = WorkspaceManager(output_dir)

        # Initialize TTS service (with gateway support)
        tts_callable = gateway.tts if (gateway and gateway.tts) else None
        self.tts_service = TTSService(tts_callable)
        self._tts = tts_callable  # Keep for backwards compatibility

        # Initialize Visual service
        if gateway:
            generate_fn = gateway.generate_images_from_prompts
            copy_fn = gateway.copy_user_provided_media
        else:
            generate_fn = None
            copy_fn = None
        modify_fn = gateway.modify_images if (gateway and gateway.modify_images) else None
        self.visual_service = VisualService(
            generate_images_from_prompts=generate_fn,
            copy_user_provided_media=copy_fn,
            modify_images=modify_fn,
            provider_manager=provider_manager,
            provider_registry=provider_registry,
        )
        # Keep for backwards compatibility
        self._generate_from_prompts = generate_fn
        self._copy_provided_images = copy_fn
        self._modify_images = modify_fn

        # Initialize Assembly service (with gateway support)
        assembler_callable = gateway.assemble_video if (gateway and gateway.assemble_video) else None
        final_subtitle_backend = subtitle_backend
        if not final_subtitle_backend and gateway and gateway.subtitle_backend:
            final_subtitle_backend = gateway.subtitle_backend
        if not final_subtitle_backend:
            if FFmpegSubtitleBackend is not None:
                try:
                    final_subtitle_backend = FFmpegSubtitleBackend()
                except Exception:
                    final_subtitle_backend = None
            else:
                try:
                    from src.backends.ffmpeg_subtitle_backend import (
                        FFmpegSubtitleBackend as _RealFFmpeg,
                    )

                    final_subtitle_backend = _RealFFmpeg()
                except Exception:
                    final_subtitle_backend = None
        self.assembly_service = AssemblyService(
            assemble_video=assembler_callable,
            subtitle_backend=final_subtitle_backend,
        )
        self._assembler_fn = assembler_callable  # Keep for backwards compatibility
        self._subtitle_backend = final_subtitle_backend  # Keep for backwards compatibility


    def create_video(
        self, 
        config: VideoConfiguration, 
        uploaded_background_music: Optional[Dict[str, bytes]] = None, 
        uploaded_images: Optional[Dict[str, bytes]] = None
    ) -> Dict[str, Any]:
        logger.info("=== Starting video generation: %s ===", config.title)

        # Step 1: Workspace
        output_base = self.workspace_manager.resolve_output_directory(config)
        workspace = self.workspace_manager.validate_and_prepare_workspace(
            config, output_base
        )
        merged_config = config_loader.load()
        final_width, final_height, aspect_ratio = _resolve_dimensions_and_orientation(config)

        context = VideoContext(
            config=config,
            output_dir=output_base,
            workspace=workspace,
            width=final_width,
            height=final_height,
            merged_config=merged_config,
            logger=logger,
        )

        # Step 2: TTS
        audio_path = self.tts_service.run_tts_audio(config, workspace, context)

        # Step 3: Prepare background music (we need this for duration resolution if no speech)
        background_music = self.assembly_service.prepare_background_music(
            config, workspace, uploaded_background_music
        )

        # Step 4: Duration
        total_duration = resolve_total_duration(
            config.length_seconds, 
            audio_path, 
            background_music, 
            logger
        )
        context.duration = total_duration

        # Step 5: Visuals
        visual_files = self.visual_service.prepare_visuals_with_modifications(
            config, workspace, aspect_ratio, final_width, final_height, uploaded_images
        )
        if not visual_files:
            raise ValueError("No visual assets available. Provide images or text prompts.")

        # Step 6: Subtitles
        segments = self.assembly_service.generate_subtitle_segments(
            config, total_duration
        )

        # Step 7: Assembly
        final_dir = workspace / "final"
        final_dir.mkdir(parents=True, exist_ok=True)
        visual_durations = _compute_visual_durations(
            config, visual_files, total_duration
        )
        output_path = self.assembly_service.assemble_and_burn_video(
            config,
            audio_path,
            visual_files,
            background_music,
            final_dir,
            final_width,
            final_height,
            segments,
            total_duration,
            visual_durations,
        )

        logger.info("=== Video complete: %s ===", output_path)

        # Step 8: Cleanup
        self.workspace_manager.cleanup_workspace(workspace)

        return {
            "output_path": output_path,
            "title": config.title,
            "format": config.output_format.value,
            "subtitles_enabled": config.subtitles_enabled,
        }

    # -------------------------------
    # Backwards-compatible methods (deprecated)
    # -------------------------------

    def _resolve_output_directory(self, config: VideoConfiguration, default_output_dir: Path) -> Path:
        warnings.warn(
            "VideoOrchestrator._resolve_output_directory is deprecated and will be removed in a future version. Use WorkspaceManager.resolve_output_directory instead.",
            FutureWarning,
            stacklevel=2,
        )
        # For backwards compatibility, delegate to workspace_manager
        return self.workspace_manager.resolve_output_directory(config)

    def _validate_and_prepare_workspace(self, config: VideoConfiguration, base_dir: Optional[Path] = None) -> Path:
        warnings.warn(
            "VideoOrchestrator._validate_and_prepare_workspace is deprecated and will be removed in a future version. Use WorkspaceManager.validate_and_prepare_workspace instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.workspace_manager.validate_and_prepare_workspace(config, base_dir)

    def _run_tts_audio(self, config: VideoConfiguration, workspace: Path, context: Optional[VideoContext] = None) -> str:
        warnings.warn(
            "VideoOrchestrator._run_tts_audio is deprecated and will be removed in a future version. Use TTSService.run_tts_audio instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.tts_service.run_tts_audio(config, workspace, context)

    def _resolve_dimensions_and_orientation(self, config: VideoConfiguration) -> tuple:
        warnings.warn(
            "VideoOrchestrator._resolve_dimensions_and_orientation is deprecated and will be removed in a future version. Use the top-level function _resolve_dimensions_and_orientation instead.",
            FutureWarning,
            stacklevel=2,
        )
        return _resolve_dimensions_and_orientation(config)

    def _prepare_visuals(self, *args, **kwargs) -> List[str]:
        warnings.warn(
            "VideoOrchestrator._prepare_visuals is deprecated and will be removed in a future version. Use VisualService.prepare_visuals instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.visual_service.prepare_visuals(*args, **kwargs)

    def _prepare_visuals_with_modifications(self, *args, **kwargs) -> List[str]:
        warnings.warn(
            "VideoOrchestrator._prepare_visuals_with_modifications is deprecated and will be removed in a future version. Use VisualService.prepare_visuals_with_modifications instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.visual_service.prepare_visuals_with_modifications(*args, **kwargs)

    def _generate_subtitle_segments(self, config: VideoConfiguration, total_duration: Optional[float]) -> List[Dict]:
        warnings.warn(
            "VideoOrchestrator._generate_subtitle_segments is deprecated and will be removed in a future version. Use AssemblyService.generate_subtitle_segments instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.assembly_service.generate_subtitle_segments(config, total_duration)

    def _prepare_background_music(self, config: VideoConfiguration, workspace: Path) -> Optional[str]:
        warnings.warn(
            "VideoOrchestrator._prepare_background_music is deprecated and will be removed in a future version. Use AssemblyService.prepare_background_music instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.assembly_service.prepare_background_music(config, workspace)

    def _assemble_and_burn_video(self, *args, **kwargs) -> str:
        warnings.warn(
            "VideoOrchestrator._assemble_and_burn_video is deprecated and will be removed in a future version. Use AssemblyService.assemble_and_burn_video instead.",
            FutureWarning,
            stacklevel=2,
        )
        return self.assembly_service.assemble_and_burn_video(*args, **kwargs)

    def _cleanup_workspace(self, workspace: Path) -> None:
        warnings.warn(
            "VideoOrchestrator._cleanup_workspace is deprecated and will be removed in a future version. Use WorkspaceManager.cleanup_workspace instead.",
            FutureWarning,
            stacklevel=2,
        )
        self.workspace_manager.cleanup_workspace(workspace)

    # -------------------------------
    # Upload validation helpers
    # -------------------------------
    def _validate_upload_size(self, data: bytes, max_size: int, file_label: str) -> None:
        from src.upload_service import UploadService
        return UploadService()._validate_upload_size(data, max_size, file_label)

    def _validate_upload_extension(self, filename: str, allowed_types: list, file_label: str) -> None:
        from src.upload_service import UploadService
        return UploadService()._validate_upload_extension(filename, allowed_types, file_label)

    def _save_uploaded_images(self, uploads: dict, dest_dir: str) -> List[str]:
        from src.upload_service import UploadService
        return UploadService().save_uploaded_images(uploads, dest_dir)

    def _save_uploaded_audio(self, uploads: dict, dest_dir: str) -> str:
        from src.upload_service import UploadService
        return UploadService().save_uploaded_audio(uploads, dest_dir)

    def _copy_background_music_to_workspace(self, music_path: str, workspace: Path) -> str:
        return self.assembly_service._copy_background_music_to_workspace(music_path, workspace)


