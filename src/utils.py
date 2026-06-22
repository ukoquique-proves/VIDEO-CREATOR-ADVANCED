"""
Shared utilities for the VideoCreation pipeline.
"""

import re


def sanitize_filename(title: str) -> str:
    """Return a filesystem-safe version of *title* for use in filenames and paths.

    Replaces spaces with underscores and strips characters that are
    illegal on Linux, macOS, or Windows (/ \\ : * ? " < > | and null bytes).
    Collapses consecutive underscores and strips leading/trailing ones.
    Returns ``"untitled"`` if the result is empty.
    """
    # Replace path-separators and other illegal characters with underscore
    sanitized = re.sub(r'[/\\:*?"<>|\x00]', "_", title)
    # Replace runs of dots (which can be used for directory traversal) with underscores
    sanitized = re.sub(r"\.+", "_", sanitized)
    sanitized = sanitized.replace(" ", "_")
    # Collapse repeated underscores and trim
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    # Defensive: avoid dot-only or traversal-style names — fall back to untitled
    if sanitized in ("", ".", ".."):
        return "untitled"
    return sanitized


def sanitize_filename_preserve_extension(filename: str) -> str:
    """Return a filesystem-safe filename while preserving the extension.

    This is useful for user-uploaded files where the suffix should remain
    intact (e.g. ``speech.mp3`` or ``image.png``).
    """
    from pathlib import Path

    path = Path(filename)
    suffix = path.suffix
    if suffix:
        base = sanitize_filename(path.stem)
        ext = sanitize_filename(suffix.lstrip("."))
        if not base:
            base = "file"
        if ext:
            return f"{base}.{ext}"
        return base
    return sanitize_filename(filename)


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v"}


def is_video_file(path: str) -> bool:
    """Return True if the file at *path* has a recognized video extension."""
    from pathlib import Path
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS
