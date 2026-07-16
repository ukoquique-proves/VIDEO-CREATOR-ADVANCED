"""
Subtitle Adapter — generates timed subtitle segments from plain text.

Uses a simple word-rate estimation model.  Can be upgraded later to
Whisper-based forced alignment (Phase 4).
"""

import logging
import re
import warnings
from typing import Dict, List, Optional

from src import config_loader

logger = logging.getLogger(__name__)


from src.schema import VideoContext

def generate_subtitle_segments(
    *args,
    **kwargs
) -> List[Dict]:
    """Split text into timed subtitle segments.

    The preferred call style is keyword-based, for example:
    generate_subtitle_segments(text="Hello", total_duration=5.0, context=context)

    Legacy positional calls that pass a VideoContext as the first argument are
    still supported for compatibility, but they emit a DeprecationWarning.
    """
    if args and isinstance(args[0], VideoContext):
        warnings.warn(
            "Passing VideoContext positionally to generate_subtitle_segments() is deprecated; use context=... instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        context = args[0]
        text = args[1] if len(args) > 1 else kwargs.pop("text", None)
        total_duration = args[2] if len(args) > 2 else kwargs.pop("total_duration", None)
        words_per_second = args[3] if len(args) > 3 else kwargs.pop("words_per_second", None)
        max_words_per_chunk = args[4] if len(args) > 4 else kwargs.pop("max_words_per_chunk", None)
        start_offset = args[5] if len(args) > 5 else kwargs.pop("start_offset", 0.0)
        
        cfg = context.merged_config.get("subtitles", {})
        use_logger = context.logger
    else:
        context = None
        text = args[0] if len(args) > 0 else kwargs.pop("text", None)
        total_duration = args[1] if len(args) > 1 else kwargs.pop("total_duration", None)
        words_per_second = args[2] if len(args) > 2 else kwargs.pop("words_per_second", None)
        max_words_per_chunk = args[3] if len(args) > 3 else kwargs.pop("max_words_per_chunk", None)
        start_offset = args[4] if len(args) > 4 else kwargs.pop("start_offset", 0.0)
        
        cfg = config_loader.subtitles()
        use_logger = logger
        
    if words_per_second is None:
        words_per_second = cfg.get("words_per_second", 2.5)
    if max_words_per_chunk is None:
        max_words_per_chunk = cfg.get("max_words_per_chunk", 8)

    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    sentences = [s for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]

    for sentence in sentences:
        s_words = sentence.split()
        while s_words:
            chunk_words = s_words[:max_words_per_chunk]
            s_words = s_words[max_words_per_chunk:]
            chunks.append(" ".join(chunk_words))

    if not chunks:
        chunks = [text.strip()]

    raw_durations = [len(c.split()) / words_per_second for c in chunks]
    total_raw = sum(raw_durations)

    if total_duration is not None and total_duration > 0 and total_raw > 0:
        scale = total_duration / total_raw
        durations = [d * scale for d in raw_durations]
    else:
        durations = raw_durations

    segments: List[Dict] = []
    cursor = 0.0
    for chunk, dur in zip(chunks, durations):
        # Compute start relative to the true unshifted schedule so that
        # a negative start_offset produces a bounded overlap of |start_offset|
        # between adjacent segments without compounding over multiple segments.
        start = max(0.0, cursor + start_offset)
        end = start + dur
        segments.append({
            "text": chunk,
            "start": round(start, 3),
            "end": round(end, 3),
            "duration_estimate": round(dur, 3),
        })
        cursor += dur

    use_logger.info(
        "Generated %d subtitle segments (total %.1fs).",
        len(segments),
        cursor,
    )
    return segments
