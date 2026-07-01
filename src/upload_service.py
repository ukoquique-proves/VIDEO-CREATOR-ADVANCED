"""
UploadService — handles validation and saving of uploaded media (images, audio).
"""

import logging
import os
from pathlib import Path
from typing import List

from src import config_loader
from src.utils import sanitize_filename_preserve_extension


logger = logging.getLogger(__name__)


class UploadService:
    """
    Service for validating and saving uploaded media (images/audio).
    """

    def _validate_upload_size(self, data: bytes, max_size: int, file_label: str) -> None:
        if len(data) > max_size:
            raise ValueError(
                f"Uploaded {file_label} too large: {len(data)} bytes (max allowed: {max_size} bytes)"
            )

    def _validate_upload_extension(self, filename: str, allowed_types: list, file_label: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in allowed_types:
            raise ValueError(
                f"Invalid {file_label} type: {ext}. Allowed types: {', '.join(allowed_types)}"
            )

    def save_uploaded_images(self, uploads: dict, dest_dir: str) -> List[str]:
        """Write in-memory image bytes to dest_dir, with validation."""
        cfg = config_loader.load().get("uploads", {})
        max_size = cfg.get("max_image_size", 52428800)  # default 50MB
        allowed_types = cfg.get(
            "allowed_image_types", [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"]
        )

        saved: List[str] = []
        for filename, data in uploads.items():
            self._validate_upload_size(data, max_size, "image")
            self._validate_upload_extension(filename, allowed_types, "image")

            safe_name = sanitize_filename_preserve_extension(os.path.basename(filename))
            if not safe_name:
                safe_name = "uploaded_asset"
            path = os.path.join(dest_dir, safe_name)
            with open(path, "wb") as f:
                f.write(data)
            logger.info("Saved uploaded image → %s", path)
            saved.append(path)
        return saved

    def save_uploaded_audio(self, uploads: dict, dest_dir: str) -> str:
        """Write uploaded audio bytes to dest_dir, with validation."""
        cfg = config_loader.load().get("uploads", {})
        max_size = cfg.get("max_audio_size", 104857600)  # default 100MB
        allowed_types = cfg.get(
            "allowed_audio_types", [".mp3", ".wav", ".ogg", ".aac", ".m4a", ".flac"]
        )

        if not uploads:
            raise ValueError("No uploaded background music provided.")
        if len(uploads) > 1:
            logger.warning("Multiple uploaded background music files provided; using the first one.")
        filename, data = next(iter(uploads.items()))

        self._validate_upload_size(data, max_size, "audio")
        self._validate_upload_extension(filename, allowed_types, "audio")

        safe_name = sanitize_filename_preserve_extension(os.path.basename(filename))
        if not safe_name:
            safe_name = "background_music.mp3"
        destination = os.path.join(dest_dir, safe_name)
        with open(destination, "wb") as f:
            f.write(data)
        logger.info("Saved uploaded background music → %s", destination)
        return destination
