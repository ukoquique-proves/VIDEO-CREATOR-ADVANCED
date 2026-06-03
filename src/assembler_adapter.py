"""
Assembler Adapter — video assembly bridge to Lingo_PERSONAS VideoAssembler.

Falls back to a pure-moviepy local assembly if the Lingo_PERSONAS import
is unavailable.

Subtitle rendering is delegated entirely to ``src.subtitle_renderer``, which
is independent of Lingo and fixes the descender-clipping bug present in
Lingo's caption renderer.
"""

import os
import logging
from typing import Dict, List, Optional

from src import config_loader
from src import subtitle_renderer
from src.backends import AssemblerBackend
from src.backends.lingo_assembler_backend import LingoAssemblerBackend

logger = logging.getLogger(__name__)

# Module-level default backend — instantiated once, shared across calls.
# Pass a different backend to assemble_video() to override (e.g. in tests).
_default_backend: AssemblerBackend = LingoAssemblerBackend()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assemble_video(
    audio_path: str,
    visual_files: List[str],
    segments: List[Dict],
    *,
    title: str = "untitled",
    output_dir: str = "output",
    output_format: str = "mp4",
    background_music: Optional[str] = None,
    subtitles_enabled: bool = False,
    width: Optional[int] = None,
    height: Optional[int] = None,
    backend: Optional[AssemblerBackend] = None,
) -> str:
    """Assemble a final video from audio, visuals, and optional subtitles.

    Parameters
    ----------
    backend:
        Assembler backend to use. Defaults to the module-level
        ``_default_backend`` (``LingoAssemblerBackend``). Pass an alternative
        to swap Lingo for another provider or to inject a mock in tests.

    Returns
    -------
    str
        Absolute path to the final video file.
    """
    cfg = config_loader.video()
    width = width or cfg.get("width", 1080)
    height = height or cfg.get("height", 1920)
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{title.replace(' ', '_')}.{output_format}"

    # Always assemble without captions first — subtitle_renderer handles those.
    active_backend = backend if backend is not None else _default_backend
    path = active_backend.assemble(
        audio_path=audio_path,
        visual_files=visual_files,
        title=title,
        output_dir=output_dir,
        output_filename=output_filename,
        background_music=background_music,
        width=width,
        height=height,
    )
    if path is None:
        path = _local_moviepy_assemble(
            audio_path=audio_path,
            visual_files=visual_files,
            output_dir=output_dir,
            output_filename=output_filename,
            width=width,
            height=height,
        )

    # Burn subtitles onto the assembled video using the subtitle renderer.
    if subtitles_enabled and segments:
        logger.info("Burning subtitles onto assembled video …")
        path = subtitle_renderer.burn_subtitles(
            video_path=path,
            segments=segments,
            output_dir=output_dir,
            output_filename=output_filename,
            output_format=output_format,
            width=width,
            height=height,
        )

    return path

# ---------------------------------------------------------------------------
# Local moviepy fallback  (audio + visuals only — no captions)
# ---------------------------------------------------------------------------

def _local_moviepy_assemble(
    audio_path: str,
    visual_files: List[str],
    output_dir: str,
    output_filename: str,
    width: int,
    height: int,
) -> str:
    """Assemble video using moviepy directly (no Lingo dependency).

    Produces a video without subtitles; subtitle burn-in is handled by
    ``subtitle_renderer.burn_subtitles``.
    """
    try:
        from moviepy import AudioFileClip, ImageClip, concatenate_videoclips
        from moviepy.video.fx import Resize
    except ImportError as exc:
        raise RuntimeError(
            f"moviepy is required for local video assembly but could not be imported: {exc}. "
            "Ensure moviepy==2.1.2 is installed."
        ) from exc

    logger.info("Local moviepy assembly: %d visuals + audio", len(visual_files))

    audio = AudioFileClip(audio_path)
    try:
        duration = audio.duration
        time_per_visual = duration / max(len(visual_files), 1)

        clips = []
        for vf in visual_files:
            clip = ImageClip(vf).with_duration(time_per_visual)
            clip = clip.with_effects([Resize(height=height)])
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose").with_audio(audio)
        try:
            output_path = os.path.join(output_dir, output_filename)
            fps = config_loader.video().get("fps", 30)
            video.write_videofile(
                output_path,
                fps=fps,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="ultrafast",
                logger=None,
            )
        finally:
            video.close()
    finally:
        audio.close()

    logger.info("Local assembly complete → %s", output_path)
    return output_path
