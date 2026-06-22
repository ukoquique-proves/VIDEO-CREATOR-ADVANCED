"""
Assembler Adapter — video assembly bridge to Lingo_PERSONAS VideoAssembler.

Falls back to a pure-moviepy local assembly if the Lingo_PERSONAS import
is unavailable.

Subtitle burn-in is handled by the orchestrator as a separate post-processing
step; this adapter is responsible only for assembling audio and visuals.
"""

import os
import logging
from typing import List, Optional

from src import config_loader
from src.backends import AssemblerBackend
from src.backends.lingo_assembler_backend import LingoAssemblerBackend
from src.utils import sanitize_filename, is_video_file

logger = logging.getLogger(__name__)

# Module-level cache for lazy backend initialization
_default_backend_cache: Optional[AssemblerBackend] = None


def _get_default_backend() -> AssemblerBackend:
    """Get or lazily initialize the default assembler backend.

    This function implements lazy initialization so that the potentially heavy
    LingoAssemblerBackend is not instantiated until it's actually needed.
    Once created, the backend instance is cached for reuse across calls.

    Returns
    -------
    AssemblerBackend
        The default backend instance (LingoAssemblerBackend).
    """
    global _default_backend_cache
    if _default_backend_cache is None:
        logger.debug("Lazily initializing default assembler backend (prefer Lingo, fallback to native)")
        try:
            import importlib.util

            if importlib.util.find_spec("shorts_creator.video_assembler") or importlib.util.find_spec("shorts_creator"):
                _default_backend_cache = LingoAssemblerBackend()
            else:
                from src.backends.native_assembler_backend import NativeAssemblerBackend

                _default_backend_cache = NativeAssemblerBackend()
        except Exception:
            # If anything goes wrong while selecting backends, fall back to native.
            from src.backends.native_assembler_backend import NativeAssemblerBackend

            _default_backend_cache = NativeAssemblerBackend()
    return _default_backend_cache


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assemble_video(
    audio_path: str,
    visual_files: List[str],
    *,
    title: str = "untitled",
    output_dir: str = "output",
    output_format: str = "mp4",
    background_music: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    duration: Optional[float] = None,
    backend: Optional[AssemblerBackend] = None,
) -> str:
    """Assemble audio and visuals into a video file.

    Subtitle burn-in is not handled here — the orchestrator applies it as a
    separate post-processing step via ``subtitle_renderer.burn_subtitles``.

    Parameters
    ----------
    duration : Optional[float]
        Total video duration in seconds. If provided, ensures consistent timing
        between subtitle generation and assembly. If not provided, duration is
        calculated from the audio file. This parameter ensures consistent behavior
        across the subtitle and assembly paths.
    backend:
        Assembler backend to use. Defaults to the lazily-initialized
        ``LingoAssemblerBackend`` (via ``_get_default_backend()``). Pass an alternative
        to swap Lingo for another provider or to inject a mock in tests.

    Returns
    -------
    str
        Absolute path to the assembled video file.
    """
    cfg = config_loader.video()
    if width is None:
        width = cfg.get("width", 1080)
    if height is None:
        height = cfg.get("height", 1920)
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{sanitize_filename(title)}.{output_format}"

    active_backend = backend if backend is not None else _get_default_backend()
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
        logger.warning("Lingo assembler unavailable; falling back to local moviepy assembly.")
        try:
            path = _local_moviepy_assemble(
                audio_path=audio_path,
                visual_files=visual_files,
                output_dir=output_dir,
                output_filename=output_filename,
                width=width,
                height=height,
                duration=duration,
                background_music=background_music,
            )
        except RuntimeError as exc:
            # If moviepy is not available and background music was requested, raise
            # a clear error rather than silently dropping the music.
            if background_music:
                raise RuntimeError(
                    "Background music was requested but the Lingo assembler is unavailable. "
                    "Local moviepy fallback cannot preserve background music, so assembly cannot proceed."
                ) from exc
            raise

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
    duration: Optional[float] = None,
    background_music: Optional[str] = None,
) -> str:
    """Assemble video using moviepy directly (no Lingo dependency).

    ``visual_files`` may freely mix still images and short video clips —
    each entry is dispatched to ``ImageClip`` or ``VideoFileClip`` based on
    its extension (see ``src.utils.is_video_file``). Video clips are
    trimmed (if longer than their allotted slot) or looped (if shorter) to
    exactly fill it, mirroring the behavior of the optional Lingo assembler
    backend. Any audio embedded in a video clip is stripped — the narration
    track passed in as ``audio_path`` is always the sole audio source, same
    as the Lingo backend.

    Produces a video without subtitles; subtitle burn-in is handled by
    ``subtitle_renderer.burn_subtitles``.

    Parameters
    ----------
    duration : Optional[float]
        Override duration calculation. If provided, this duration is used instead
        of measuring from the audio file. This ensures consistent timing between
        subtitle generation and assembly when an explicit duration is configured.
    """
    try:
        from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips
        from moviepy.video.fx import Resize, Crop
    except ImportError as exc:
        raise RuntimeError(
            f"moviepy is required for local video assembly but could not be imported: {exc}. "
            "Ensure moviepy==2.1.2 is installed."
        ) from exc

    logger.info("Local moviepy assembly: %d visuals + audio", len(visual_files))

    output_path = os.path.join(output_dir, output_filename)
    audio = AudioFileClip(audio_path)
    clips: List = []
    bg = None
    try:
        # Use provided duration if available, otherwise calculate from audio
        if duration is not None:
            total_duration = duration
            logger.info("Using provided duration for assembly: %.2fs", total_duration)
        else:
            total_duration = audio.duration
            logger.info("Calculated duration from audio: %.2fs", total_duration)

        time_per_visual = total_duration / max(len(visual_files), 1)

        for vf in visual_files:
            clip = _build_visual_clip(
                vf, time_per_visual, width, height,
                ImageClip=ImageClip, VideoFileClip=VideoFileClip,
                concatenate_videoclips=concatenate_videoclips,
                Resize=Resize, Crop=Crop,
            )
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")

        # If background music is provided, loop it to the total duration and mix
        if background_music:
            try:
                from moviepy import CompositeAudioClip
                from moviepy.audio.fx import AudioLoop, MultiplyVolume

                bg = AudioFileClip(background_music)
                bg_looped = bg.with_effects(
                    [AudioLoop(duration=total_duration), MultiplyVolume(0.15)]
                )
                composite = CompositeAudioClip([audio, bg_looped])
                video = video.with_audio(composite)
            except Exception as exc:
                logger.warning(
                    "Background music could not be mixed (%s); continuing with narration only.",
                    exc,
                )
                video = video.with_audio(audio)
        else:
            video = video.with_audio(audio)
        try:
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
        if bg is not None:
            try:
                bg.close()
            except Exception:
                pass
        audio.close()
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass

    logger.info("Local assembly complete → %s", output_path)
    return output_path


def _build_visual_clip(
    file_path: str,
    slot_duration: float,
    width: int,
    height: int,
    *,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    Resize,
    Crop,
):
    """Build a single timeline clip from an image or video file.

    Image files become a static ``ImageClip`` held for ``slot_duration``.
    Video files become a ``VideoFileClip`` with its own audio stripped,
    trimmed to ``slot_duration`` if longer, or looped (by concatenating
    whole copies of itself) if shorter — never stretched/sped up. The
    result is then resized and center-cropped to exactly (width, height).
    """
    if is_video_file(file_path):
        clip = VideoFileClip(file_path).without_audio()
        if clip.duration <= 0:
            logger.warning(
                "Video clip reports zero/invalid duration, treating as a "
                "still frame instead: %s", file_path,
            )
            clip.close()
            clip = ImageClip(file_path).with_duration(slot_duration)
        elif clip.duration < slot_duration:
            loops_needed = int(slot_duration / clip.duration) + 1
            clip = concatenate_videoclips([clip] * loops_needed).subclipped(0, slot_duration)
        else:
            clip = clip.subclipped(0, slot_duration)
    else:
        clip = ImageClip(file_path).with_duration(slot_duration)

    return _fit_to_frame(clip, width, height, Resize=Resize, Crop=Crop)


def _fit_to_frame(clip, width: int, height: int, *, Resize, Crop):
    """Resize *clip* so its smaller dimension matches the target frame, then
    center-crop to exactly (width, height). Shared by image and video clips
    so both fill the frame identically (no letterboxing/stretching).
    """
    src_w, src_h = clip.size
    target_ratio = width / height
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        clip = clip.with_effects([Resize(height=height)])
    else:
        clip = clip.with_effects([Resize(width=width)])

    rw, rh = clip.size
    clip = clip.with_effects([Crop(width=width, height=height, x_center=rw // 2, y_center=rh // 2)])
    return clip
