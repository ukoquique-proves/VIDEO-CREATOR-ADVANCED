"""
UploadService — handles validation and saving of uploaded media (images, audio).
"""

import logging
import os
from pathlib import Path
from typing import List, Dict, Tuple

from src import config_loader
from src.utils import sanitize_filename_preserve_extension


logger = logging.getLogger(__name__)

# Magic bytes (file signatures) for common image formats
IMAGE_MAGIC_BYTES: Dict[str, List[bytes]] = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".webp": [b"RIFF", b"WEBP"],
    ".bmp": [b"BM"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
}

# Magic bytes for common audio formats
AUDIO_MAGIC_BYTES: Dict[str, List[bytes]] = {
    ".mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
    ".wav": [b"RIFF", b"WAVE"],
    ".ogg": [b"OggS"],
    ".aac": [b"\xff\xf1", b"\xff\xf9"],
    ".m4a": [b"\x00\x00\x00", b"ftyp"],
    ".flac": [b"fLaC"],
}


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
    
    def _validate_magic_bytes(self, data: bytes, ext: str, magic_map: Dict[str, List[bytes]], file_label: str) -> None:
        """Validate file content against magic bytes (file signature)."""
        expected_magics = magic_map.get(ext, [])
        if not expected_magics:
            return  # Skip validation if we don't have magic bytes for this type
        
        # Check if data starts with any of the expected magic bytes
        matches = any(data.startswith(magic) for magic in expected_magics)
        
        # Special case for formats like WebP/WAV which have "RIFF" followed by another string
        if not matches and ext in [".webp", ".wav"]:
            if ext == ".webp" and len(data) >= 12:
                matches = data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            elif ext == ".wav" and len(data) >= 12:
                matches = data[:4] == b"RIFF" and data[8:12] == b"WAVE"
        
        if not matches:
            raise ValueError(
                f"Invalid {file_label} content for type {ext}. File signature doesn't match expected format."
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
            ext = Path(filename).suffix.lower()
            self._validate_upload_extension(filename, allowed_types, "image")
            self._validate_magic_bytes(data, ext, IMAGE_MAGIC_BYTES, "image")

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
        ext = Path(filename).suffix.lower()
        self._validate_upload_extension(filename, allowed_types, "audio")
        self._validate_magic_bytes(data, ext, AUDIO_MAGIC_BYTES, "audio")

        safe_name = sanitize_filename_preserve_extension(os.path.basename(filename))
        if not safe_name:
            safe_name = "background_music.mp3"
        destination = os.path.join(dest_dir, safe_name)
        with open(destination, "wb") as f:
            f.write(data)
        logger.info("Saved uploaded background music → %s", destination)
        return destination
