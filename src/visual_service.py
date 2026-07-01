"""
VisualService — handles visual asset preparation and modification.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict

from src.schema import VideoConfiguration, VisualAssetType
from src import image_adapter
from src.image_providers.manager import ProviderManager
from src.utils import is_video_file
from src.upload_service import UploadService


logger = logging.getLogger(__name__)


class VisualService:
    """
    Service for preparing and modifying visual assets (images/videos).
    """

    def __init__(
        self,
        generate_from_prompts=None,
        copy_provided_images=None,
        modify_images=None,
        provider_manager: Optional[ProviderManager] = None,
    ):
        self._generate_from_prompts = generate_from_prompts
        self._copy_provided_images = copy_provided_images
        self._modify_images = modify_images
        self._provider_manager = provider_manager
        self._upload_service = UploadService()

    def prepare_visuals(
        self, config: VideoConfiguration, workspace: str, aspect_ratio: str, width: int, height: int, uploaded_images: Optional[Dict[str, bytes]] = None
    ) -> List[str]:
        """
        Resolve visual assets — either copy provided images or generate from prompts.
        """
        visuals_dir = os.path.join(workspace, "visuals")
        os.makedirs(visuals_dir, exist_ok=True)

        if config.visual_assets.asset_type in (
            VisualAssetType.IMAGE_SEQUENCE,
            VisualAssetType.MEDIA_SEQUENCE,
        ):
            images = list(config.visual_assets.images or [])

            if uploaded_images:
                images.extend(
                    self._upload_service.save_uploaded_images(
                        uploaded_images, visuals_dir
                    )
                )

            if not images:
                logger.warning(
                    "%s selected but no files provided.", config.visual_assets.asset_type.value
                )
                return []

            copy_fn = self._copy_provided_images or image_adapter.copy_provided_images
            resolved = copy_fn(images, visuals_dir)

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

        if self._generate_from_prompts:
            return self._generate_from_prompts(
                prompts,
                visuals_dir,
                style=config.image_style,
                engine=config.image_engine.value if config.image_engine else None,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
            )
        else:
            return image_adapter.generate_from_prompts(
                prompts,
                visuals_dir,
                style=config.image_style,
                engine=config.image_engine.value if config.image_engine else None,
                aspect_ratio=aspect_ratio,
                width=width,
                height=height,
                provider_manager=self._provider_manager,
            )

    def prepare_visuals_with_modifications(
        self, config: VideoConfiguration, workspace: Path, aspect_ratio: str, width: int, height: int, uploaded_images: Optional[Dict[str, bytes]] = None
    ) -> List[str]:
        """Prepare visuals and apply optional modifications."""
        logger.info("[2/4] Preparing visual assets…")
        visual_files = self.prepare_visuals(
            config, str(workspace), aspect_ratio, width, height, uploaded_images
        )

        if config.image_modification_instructions:
            logger.info("[+] Applying image modifications…")
            modify_fn = self._modify_images or image_adapter.modify_images
            visual_files = modify_fn(visual_files, config.image_modification_instructions)
        else:
            logger.debug("Image modifications skipped (no instructions provided).")

        return visual_files
