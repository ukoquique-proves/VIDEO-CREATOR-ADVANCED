"""
Subtitle Adapter — generates timed subtitle segments from plain text.

Uses a simple word-rate estimation model.  Can be upgraded later to
Whisper-based forced alignment (Phase 4).
"""

import logging
import re
from typing import Dict, List, Optional

from src import config_loader

logger = logging.getLogger(__name__)


def generate_subtitle_segments(
    text: str,
    total_duration: Optional[float] = None,
    words_per_second: Optional[float] = None,
    max_words_per_chunk: Optional[int] = None,
) -> List[Dict]:
    """Split *text* into timed subtitle segments.

    Parameters
    ----------
    text:
        Full speech content.
    total_duration:
        If provided, segments are scaled to fit this duration exactly.
    words_per_second:
        Estimated speaking rate. Defaults to config value (2.5).
    max_words_per_chunk:
        Maximum words per subtitle line. Defaults to config value (10).

    Returns
    -------
    list[dict]
        Each dict has keys ``text``, ``start``, ``end``, ``duration_estimate``.
    """
    cfg = config_loader.subtitles()
    words_per_second = words_per_second or cfg.get("words_per_second", 2.5)
    max_words_per_chunk = max_words_per_chunk or cfg.get("max_words_per_chunk", 10)

    words = text.split()
    if not words:
        return []

    # Split into chunks
    chunks: List[str] = []
    # Try to split on sentence boundaries first; filter empty strings that can
    # result from trailing punctuation + whitespace before/after strip()
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]

    for sentence in sentences:
        s_words = sentence.split()
        while s_words:
            chunk_words = s_words[:max_words_per_chunk]
            s_words = s_words[max_words_per_chunk:]
            chunks.append(" ".join(chunk_words))

    if not chunks:
        chunks = [text.strip()]

    # Estimate duration for each chunk
    raw_durations = [len(c.split()) / words_per_second for c in chunks]
    total_raw = sum(raw_durations)

    # Scale to fit total_duration if provided
    if total_duration and total_raw > 0:
        scale = total_duration / total_raw
        durations = [d * scale for d in raw_durations]
    else:
        durations = raw_durations

    # Build segments
    segments: List[Dict] = []
    cursor = 0.0
    for chunk, dur in zip(chunks, durations):
        segments.append({
            "text": chunk,
            "start": round(cursor, 3),
            "end": round(cursor + dur, 3),
            "duration_estimate": round(dur, 3),
        })
        cursor += dur

    logger.info(
        "Generated %d subtitle segments (total %.1fs).",
        len(segments),
        cursor,
    )
    return segments
