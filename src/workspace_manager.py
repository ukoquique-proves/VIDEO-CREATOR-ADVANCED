"""
WorkspaceManager — handles workspace setup, output directory resolution, and cleanup.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

from src.schema import VideoConfiguration, VisualAssetType
from src.utils import sanitize_filename


logger = logging.getLogger(__name__)


def _sanitize_title(title: str) -> str:
    """Alias for src.utils.sanitize_filename — kept for internal use."""
    return sanitize_filename(title)


class WorkspaceManager:
    """
    Manages workspace setup, output directory resolution, and cleanup.
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def resolve_output_directory(self, config: VideoConfiguration) -> Path:
        """
        Determine the output directory based on config and visual assets.

        If save_to_source_folder is True and assets are local (IMAGE_SEQUENCE or MEDIA_SEQUENCE),
        use the directory of the first asset. Otherwise, use the default output directory.
        """
        if not config.save_to_source_folder:
            return self.output_dir

        if config.visual_assets.asset_type == VisualAssetType.TEXT_PROMPTS:
            return self.output_dir

        images = config.visual_assets.images or []
        if images:
            first_image_path = Path(images[0])
            if first_image_path.exists():
                output_dir = first_image_path.parent
                logger.info("[1/10] Output directory set to source folder: %s", output_dir)
                return output_dir

        return self.output_dir

    def validate_and_prepare_workspace(self, config: VideoConfiguration, base_dir: Optional[Path] = None) -> Path:
        """
        Validate title for path traversal attacks and create the workspace.
        """
        if base_dir is None:
            base_dir = self.output_dir
        raw_title = str(config.title or "")
        if ".." in raw_title or "/" in raw_title or "\\" in raw_title or Path(raw_title).is_absolute():
            raise ValueError("Invalid video title resulting in an unsafe workspace path.")

        sanitized = _sanitize_title(config.title)
        workspace = base_dir / sanitized
        try:
            resolved_workspace = workspace.resolve()
            base = base_dir.resolve()
            resolved_workspace.relative_to(base)
        except Exception:
            raise ValueError("Invalid video title resulting in an unsafe workspace path.")

        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def cleanup_workspace(self, workspace: Path) -> None:
        """
        Remove transient files from the workspace directory.

        Deletes temp/ subdirectory (if present) and any moviepy scratch files
        matching *TEMP_MPY*. All other workspace contents are left in place.
        """
        temp_dir = workspace / "temp"
        if temp_dir.exists():
            logger.info("Cleaning up temporary directory: %s", temp_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)

        for transient in workspace.glob("*TEMP_MPY*"):
            try:
                transient.unlink()
                logger.info("Removed transient file: %s", transient)
            except Exception as e:
                logger.warning("Could not remove transient file %s: %s", transient, e)
