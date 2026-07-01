
"""
Assembler Adapter — native video assembly bridge.

Uses a pure-moviepy local implementation.

Subtitle burn-in is handled by the orchestrator as a separate post-processing
step; this adapter is responsible only for assembling audio and visuals.
"""

import os
import logging
from typing import List, Optional

from src import config_loader
from src.backends import AssemblerBackend
from src.backends.native_assembler_backend import NativeAssemblerBackend
from src.utils import sanitize_filename, is_video_file

logger = logging.getLogger(__name__)

# Module-level cache for lazy backend initialization
_default_backend_cache: Optional[AssemblerBackend] = None


def _get_default_backend() -> AssemblerBackend:
    """Get or lazily initialize the default assembler backend.

    This function implements lazy initialization so that heavy backends
    are not instantiated until needed. The native MoviePy backend
    is the default and sole implementation.
    """
    global _default_backend_cache
    if _default_backend_cache is None:
        logger.debug("Lazily initializing default assembler backend (native MoviePy)")
        _default_backend_cache = NativeAssemblerBackend()
    return _default_backend_cache


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

from src.schema import VideoContext

def assemble_video(
    *args,
    **kwargs
) -> str:
    """Assemble audio and visuals into a video file.
    Supports both old (without context) and new (with context first) calling styles.
    """
    if args and isinstance(args[0], VideoContext):
        context = args[0]
        audio_path = args[1] if len(args) > 1 else kwargs.pop("audio_path", None)
        visual_files = args[2] if len(args) > 2 else kwargs.pop("visual_files", None)
        title = args[3] if len(args) > 3 else kwargs.pop("title", "untitled")
        output_dir = args[4] if len(args) > 4 else kwargs.pop("output_dir", "output")
        output_format = args[5] if len(args) > 5 else kwargs.pop("output_format", "mp4")
        background_music = args[6] if len(args) > 6 else kwargs.pop("background_music", None)
        width = args[7] if len(args) > 7 else kwargs.pop("width", None)
        height = args[8] if len(args) > 8 else kwargs.pop("height", None)
        duration = args[9] if len(args) > 9 else kwargs.pop("duration", None)
        backend = args[10] if len(args) > 10 else kwargs.pop("backend", None)
        
        cfg = context.merged_config.get("video", {})
        use_logger = context.logger
    else:
        context = None
        audio_path = args[0] if len(args) > 0 else kwargs.pop("audio_path", None)
        visual_files = args[1] if len(args) > 1 else kwargs.pop("visual_files", None)
        title = args[2] if len(args) > 2 else kwargs.pop("title", "untitled")
        output_dir = args[3] if len(args) > 3 else kwargs.pop("output_dir", "output")
        output_format = args[4] if len(args) > 4 else kwargs.pop("output_format", "mp4")
        background_music = args[5] if len(args) > 5 else kwargs.pop("background_music", None)
        width = args[6] if len(args) > 6 else kwargs.pop("width", None)
        height = args[7] if len(args) > 7 else kwargs.pop("height", None)
        duration = args[8] if len(args) > 8 else kwargs.pop("duration", None)
        backend = args[9] if len(args) > 9 else kwargs.pop("backend", None)
        
        cfg = config_loader.video()
        use_logger = logger
        
    if width is None:
        width = cfg.get("width", 1080)
    if height is None:
        height = cfg.get("height", 1920)
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{sanitize_filename(title)}.{output_format}"

    visual_durations = kwargs.pop("visual_durations", None)

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
        duration=duration,
        visual_durations=visual_durations,
    )

    if path is None:
        raise RuntimeError("Video assembly failed to produce an output.")

    return path


def local_moviepy_assemble(
    audio_path: str,
    visual_files: List[str],
    output_dir: str,
    output_filename: str,
    width: int,
    height: int,
    duration: Optional[float] = None,
    background_music: Optional[str] = None,
    merged_config = None,
    log = None,
    visual_durations: Optional[List[float]] = None,
) -> str:
    """Public helper for native backends to invoke the local MoviePy assembler."""
    return _local_moviepy_assemble(
        audio_path=audio_path,
        visual_files=visual_files,
        output_dir=output_dir,
        output_filename=output_filename,
        width=width,
        height=height,
        duration=duration,
        background_music=background_music,
        merged_config=merged_config,
        log=log,
        visual_durations=visual_durations,
    )


# ---------------------------------------------------------------------------
# Local moviepy implementation (audio + visuals only — no captions)
# ---------------------------------------------------------------------------

class MoviePyProgressLogger:
    """Custom logger compatible with MoviePy 2.x progress callback.

    MoviePy 2.x calls ``logger(t)`` where *t* is elapsed time in seconds.
    We track progress as a percentage of total_frames/fps.
    """
    def __init__(self, log, total_frames, fps=30):
        self.log = log
        self.total_frames = total_frames
        self.fps = fps
        self.last_percent = -10

    def __call__(self, t):
        """Called by MoviePy with elapsed time *t* in seconds."""
        if self.total_frames > 0 and self.fps > 0:
            current_frame = int(t * self.fps)
            percent = min(int((current_frame / self.total_frames) * 100), 100)
            if percent >= self.last_percent + 10:
                self.last_percent = percent
                self.log.info(
                    "Video assembly progress: %d%% complete (%d/%d frames)",
                    percent, current_frame, self.total_frames,
                )


def _local_moviepy_assemble(
    audio_path: str,
    visual_files: List[str],
    output_dir: str,
    output_filename: str,
    width: int,
    height: int,
    duration: Optional[float] = None,
    background_music: Optional[str] = None,
    merged_config = None,
    log = logger,
    visual_durations: Optional[List[float]] = None,
) -> str:
    """Assemble video using moviepy directly (no external dependencies).

    ``visual_files`` may freely mix still images and short video clips —
    each entry is dispatched to ``ImageClip`` or ``VideoFileClip`` based on
    its extension (see ``src.utils.is_video_file``). Video clips are
    trimmed (if longer than their allotted slot) or looped (if shorter) to
    exactly fill it. Any audio embedded in a video clip is stripped — the narration
    track passed in as ``audio_path`` is always the sole audio source.

    Produces a video without subtitles; subtitle burn-in is handled by
    ``subtitle_renderer.burn_subtitles``.

    Parameters
    ----------
    duration : Optional[float]
        Override duration calculation. If provided, this duration is used instead
        of measuring from the audio file. This ensures consistent timing between
        subtitle generation and assembly when an explicit duration is configured.
    visual_durations : Optional[List[float]]
        Per-visual display duration in seconds. When provided, each visual is
        shown for exactly the specified duration instead of an equal share of
        total_duration. The sum should equal total_duration.
    """
    try:
        from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips
        from moviepy.video.fx import Resize, Crop
    except ImportError as exc:
        raise RuntimeError(
            f"moviepy is required for video assembly but could not be imported: {exc}. "
            "Ensure moviepy==2.1.2 is installed."
        ) from exc

    log.info("Native MoviePy assembly: %d visuals + audio", len(visual_files))

    output_path = os.path.join(output_dir, output_filename)
    audio = AudioFileClip(audio_path)
    clips: List = []
    bg = None
    try:
        if duration is not None:
            total_duration = duration
            log.info("Using provided duration for assembly: %.2fs", total_duration)
        else:
            total_duration = audio.duration
            log.info("Calculated duration from audio: %.2fs", total_duration)

        time_per_visual = total_duration / max(len(visual_files), 1)
        if merged_config is not None:
            fps = merged_config.get("video", {}).get("fps", 30)
        else:
            fps = config_loader.video().get("fps", 30)

        # Use per-visual durations if provided, otherwise divide time equally
        if visual_durations and len(visual_durations) == len(visual_files):
            slot_times = visual_durations
            log.info("Using per-scene durations for assembly.")
        else:
            slot_times = [time_per_visual] * len(visual_files)

        total_visuals = len(visual_files)
        for idx, (vf, slot) in enumerate(zip(visual_files, slot_times), 1):
            log.info(f"Processing visual {idx}/{total_visuals}: {os.path.basename(vf)} ({slot:.2f}s)")
            clip = _build_visual_clip(
                vf, slot, width, height, fps,
                ImageClip=ImageClip, VideoFileClip=VideoFileClip,
                concatenate_videoclips=concatenate_videoclips,
                Resize=Resize, Crop=Crop,
            )
            clips.append(clip)

        video = concatenate_videoclips(clips, method="chain")

        if audio.duration is not None and audio.duration > total_duration:
            log.info("Subclipping narration audio from %.2fs to matching duration %.2fs", audio.duration, total_duration)
            audio = audio.subclipped(0, total_duration)

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

        total_frames = int(total_duration * fps)
        log.info(f"Starting to write video file: {total_frames} frames at {fps} fps")

        try:
            video.write_videofile(
                output_path,
                fps=fps,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="medium",
                pixel_format="yuv420p",  # Ensure high compatibility and avoid black frames on some players
                logger="bar",
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

    logger.info("Native assembly complete → %s", output_path)
    return output_path


def _build_visual_clip(
    file_path: str,
    slot_duration: float,
    width: int,
    height: int,
    fps: int,
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
        try:
            clip = VideoFileClip(file_path).without_audio()
            # Normalize FPS to ensure smooth concatenation and avoid black frames
            clip = clip.with_fps(fps)
            
            if clip.duration <= 0:
                logger.warning(
                    "Video clip reports zero/invalid duration, treating as a "
                    "still frame instead: %s", file_path,
                )
                clip.close()
                clip = ImageClip(file_path).with_duration(slot_duration).with_fps(fps)
            elif clip.duration < slot_duration:
                loops_needed = int(slot_duration / clip.duration) + 1
                # Ensure all looped parts have the same FPS
                clip = concatenate_videoclips([clip] * loops_needed).subclipped(0, slot_duration)
            else:
                clip = clip.subclipped(0, slot_duration)
        except Exception as exc:
            logger.warning("Failed to load video clip %s (%s), falling back to ImageClip", file_path, exc)
            clip = ImageClip(file_path).with_duration(slot_duration).with_fps(fps)
    else:
        clip = ImageClip(file_path).with_duration(slot_duration).with_fps(fps)

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

