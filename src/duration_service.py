"""
Duration Service — handles audio duration measurement and resolution.
"""

import json
import logging
import subprocess
from typing import Optional


logger = logging.getLogger(__name__)


def probe_audio_duration(path: str) -> float:
    """
    Measure audio file duration using ffprobe.
    
    Args:
        path: Path to audio file
        
    Returns:
        Duration in seconds
        
    Raises:
        RuntimeError: If ffprobe fails
    """
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


def resolve_total_duration(
    explicit_seconds: Optional[float], 
    audio_path: str, 
    logger_instance=None
) -> Optional[float]:
    """
    Resolve total video duration, preferring explicit seconds, then probing audio.
    
    Args:
        explicit_seconds: Explicitly requested duration in seconds (if any)
        audio_path: Path to audio file to probe if no explicit duration
        logger_instance: Logger instance to use (defaults to module logger)
        
    Returns:
        Total duration in seconds, or None if it couldn't be determined
    """
    log = logger_instance or logger
    if explicit_seconds is not None:
        log.debug("Using explicit duration: %.2fs", explicit_seconds)
        return explicit_seconds
    try:
        duration = probe_audio_duration(audio_path)
        log.info("Measured audio duration via ffprobe: %.2fs", duration)
        return duration
    except Exception as exc:
        log.warning(
            "Could not measure audio duration via ffprobe (%s) — falling back to moviepy.",
            exc,
        )
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
