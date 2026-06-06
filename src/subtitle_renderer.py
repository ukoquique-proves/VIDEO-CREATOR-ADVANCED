"""
Subtitle Renderer — Pillow-based subtitle burn-in, independent of Lingo_PERSONAS.

Exposes two public functions:
  - ``burn_subtitles()``  — composites timed subtitle frames onto an assembled video
  - ``render_subtitle_frame()`` — renders a single RGBA subtitle overlay image

Key design: line height is derived from ``font.getmetrics()`` (ascent + descent)
rather than ``textbbox``, which clips descenders for characters like p, q, g, y, j.
"""

import logging
import textwrap
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src import config_loader

logger = logging.getLogger(__name__)


def burn_subtitles(
    video_path: str,
    segments: List[Dict],
    output_dir: str,
    output_filename: str,
    output_format: str,
    width: int,
    height: int,
) -> str:
    """Composite subtitle frames onto an assembled video using alpha blending.

    Pre-renders all subtitle segments to RGBA numpy arrays, then blends them
    onto each video frame via a ``VideoClip(make_frame)`` pass. This avoids
    moviepy's RGBA compositing ambiguity and correctly preserves transparency.

    Returns
    -------
    str
        Path to the subtitled output video.
    """
    import os

    try:
        from moviepy import VideoFileClip, VideoClip
    except ImportError as exc:
        raise RuntimeError(
            f"moviepy is required for subtitle burn-in but could not be imported: {exc}. "
            "Ensure moviepy==2.1.2 is installed."
        ) from exc

    scfg = config_loader.subtitles()
    font_path = scfg.get(
        "font",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    )
    font_size    = int(scfg.get("font_size", 54))
    font_color   = scfg.get("font_color", "white")
    stroke_color = scfg.get("stroke_color", "black")
    stroke_width = min(int(scfg.get("stroke_width", 2)), 8)  # clamp: O(n²) render cost
    margin       = int(scfg.get("margin", 50))
    max_chars    = int(scfg.get("max_chars_per_line", 42))

    try:
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        logger.warning("Font not found at %s — using Pillow default.", font_path)
        font = ImageFont.load_default()

    video = VideoFileClip(video_path)
    try:
        fps = video.fps

        # Pre-render all subtitle frames as RGBA numpy arrays with their time ranges.
        rendered: List[Dict] = []
        for seg in segments:
            text  = seg.get("text", "").strip()
            start = seg.get("start", 0.0)
            end   = seg.get("end", 0.0)
            if not text or end <= start:
                continue

            frame = render_subtitle_frame(
                text=text,
                width=width,
                height=height,
                font=font,
                font_color=font_color,
                stroke_color=stroke_color,
                stroke_width=stroke_width,
                margin=margin,
                max_chars=max_chars,
            )
            rgba = np.array(frame, dtype=np.float32)  # H x W x 4, values 0-255
            rendered.append({"start": start, "end": end, "rgba": rgba})

        if not rendered:
            logger.warning(
                "burn_subtitles: no valid subtitle segments to render — "
                "returning original video without subtitles. "
                "Check that segments have non-empty text and end > start."
            )
            return video_path

        def make_frame(t: float) -> np.ndarray:
            """Alpha-blend the active subtitle onto the video frame at time t."""
            base = video.get_frame(t).astype(np.float32)  # H x W x 3, 0-255

            for r in rendered:
                if r["start"] <= t < r["end"]:
                    rgba  = r["rgba"]
                    alpha = rgba[:, :, 3:4] / 255.0  # normalise to 0-1
                    rgb   = rgba[:, :, :3]
                    base  = base * (1.0 - alpha) + rgb * alpha
                    break  # only one subtitle active at a time

            return base.clip(0, 255).astype(np.uint8)

        composite = VideoClip(make_frame, duration=video.duration)
        if video.audio is not None:
            composite = composite.with_audio(video.audio)
        else:
            logger.warning(
                "burn_subtitles: source video has no audio track — "
                "subtitled output will be silent."
            )
        try:
            output_path = os.path.join(output_dir, f"subtitled_{output_filename}")
            composite.write_videofile(
                output_path,
                fps=fps,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="ultrafast",
                logger=None,
            )
            logger.info("Subtitle burn-in complete → %s", output_path)
            return output_path
        finally:
            composite.close()
    finally:
        video.close()


def render_subtitle_frame(
    text: str,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont,
    font_color: str,
    stroke_color: str,
    stroke_width: int,
    margin: int,
    max_chars: int,
) -> Image.Image:
    """Render one subtitle frame as a transparent RGBA image.

    Line height is derived from ``font.getmetrics()`` (ascent + descent),
    which includes the full descender region. ``textbbox`` only returns the
    ink bounding box and clips descenders for characters like p, q, g, y, j.
    """
    lines = textwrap.wrap(text, width=max_chars) or [text]
    stroke_width = min(stroke_width, 8)  # clamp: O(n²) render cost

    ascent, descent = font.getmetrics()
    line_height   = ascent + descent
    line_spacing  = int(line_height * 0.2)
    total_text_height = len(lines) * line_height + (len(lines) - 1) * line_spacing

    max_line_width = max(font.getlength(line) for line in lines)
    pad_x = stroke_width + 16
    pad_y = stroke_width + 12
    box_w = int(max_line_width) + pad_x * 2
    box_h = total_text_height + pad_y * 2

    box_x = (width - box_w) // 2
    # box_y calculation changed to support "middle" position
    scfg = config_loader.subtitles()
    position = scfg.get("position", "bottom")

    if position == "middle":
        box_y = (height - box_h) // 2
    else:  # default to bottom
        box_y = height - margin - box_h

    frame = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(frame)

    draw.rounded_rectangle(
        [box_x - 4, box_y - 4, box_x + box_w + 4, box_y + box_h + 4],
        radius=12,
        fill=(0, 0, 0, 160),
    )

    y_cursor = box_y + pad_y
    for line in lines:
        line_w = font.getlength(line)
        x = box_x + pad_x + (box_w - pad_x * 2 - line_w) // 2

        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((x + dx, y_cursor + dy), line, font=font, fill=stroke_color)

        draw.text((x, y_cursor), line, font=font, fill=font_color)
        y_cursor += line_height + line_spacing

    return frame
