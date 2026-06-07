"""
FFmpeg Subtitle Backend — wraps ``src.subtitle_renderer`` behind the
``SubtitleBackend`` protocol.

Swapping to a different renderer (Whisper+SRT, GPU-accelerated, etc.)
only requires providing an alternative class that satisfies the protocol.
"""

import logging
from typing import Dict, List

from src import subtitle_renderer

logger = logging.getLogger(__name__)


class FFmpegSubtitleBackend:
    """Burns subtitles using ffmpeg and ASS format via ``subtitle_renderer``."""

    def burn_subtitles(
        self,
        video_path: str,
        segments: List[Dict],
        output_dir: str,
        output_filename: str,
        output_format: str,
        width: int,
        height: int,
    ) -> str:
        return subtitle_renderer.burn_subtitles(
            video_path=video_path,
            segments=segments,
            output_dir=output_dir,
            output_filename=output_filename,
            output_format=output_format,
            width=width,
            height=height,
        )
