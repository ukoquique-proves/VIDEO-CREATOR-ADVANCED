"""
Shared utilities for the VideoCreation pipeline.
"""

import re
import shutil
import subprocess
import logging

logger = logging.getLogger(__name__)


def check_ffmpeg_available() -> None:
    """Verify that ffmpeg and ffprobe are available on the system PATH.

    Raises RuntimeError if either binary is missing or non-executable.
    """
    for tool in ["ffmpeg", "ffprobe"]:
        if not shutil.which(tool):
            raise RuntimeError(
                f"Required tool '{tool}' not found on PATH. "
                "Please install FFmpeg and ensure it is in your system PATH."
            )
    
    # Optional: Quick version check to ensure they actually run
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        subprocess.run(["ffprobe", "-version"], capture_output=True, check=True)
    except Exception as exc:
        raise RuntimeError(
            f"FFmpeg tools found but failed to execute: {exc}"
        ) from exc


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


def callable_accepts_kwarg(callable_obj, kwarg_name: str) -> bool:
    """Check if a callable accepts a keyword argument by name."""
    import inspect
    try:
        sig = inspect.signature(callable_obj)
        params = list(sig.parameters.values())
        # Check if any parameter is keyword-only or has the name
        for param in params:
            if param.name == kwarg_name:
                return True
        # If there's **kwargs, it accepts any keyword argument
        for param in params:
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                return True
        return False
    except (ValueError, TypeError):
        # If we can't inspect the signature, err on the safe side
        return False


def callable_accepts_positional(callable_obj, num_positional: int) -> bool:
    """Check if a callable can accept at least N positional arguments."""
    import inspect
    try:
        sig = inspect.signature(callable_obj)
        params = list(sig.parameters.values())
        required = 0
        has_var_args = False
        for param in params:
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                if param.default is inspect.Parameter.empty:
                    required += 1
                else:
                    # Optional positional is fine
                    pass
            elif param.kind == inspect.Parameter.VAR_POSITIONAL:
                has_var_args = True
        # If it has *args or enough parameters
        return has_var_args or len(params) >= num_positional
    except (ValueError, TypeError):
        return False
