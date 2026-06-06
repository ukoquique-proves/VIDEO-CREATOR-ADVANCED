"""
TTS Adapter — Text-to-Speech bridge to Lingo_PERSONAS.

Supports:
  - edge_tts (free, no API key) via Lingo_PERSONAS backend
  - ffmpeg silent-audio fallback for testing / offline use
"""

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional

from src.lingo_utils import ensure_lingo_on_path
from src import config_loader
from src.schema import Language

logger = logging.getLogger(__name__)

# Default edge_tts voice per language code.
# Full list: https://speech.microsoft.com/portal/voicegallery
LANGUAGE_VOICES: dict = {
    Language.ENGLISH.value: "en-US-GuyNeural",
    Language.SPANISH.value: "es-AR-TomasNeural",   # Rioplatense Spanish (Argentina)
    Language.CHINESE.value: "zh-CN-YunxiNeural",
    Language.FRENCH.value: "fr-FR-HenriNeural",
    Language.GERMAN.value: "de-DE-ConradNeural",
    Language.PORTUGUESE.value: "pt-BR-AntonioNeural",
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_voice_mappings():
    """Ensure all languages defined in schema have a default voice mapping."""
    for lang in Language:
        if lang.value not in LANGUAGE_VOICES:
            logger.error("Missing TTS voice mapping for language: %s", lang.name)
            # We don't raise here to avoid breaking at startup, but it will log
            # an error that should be caught during development/CI.

# Validate on module import
validate_voice_mappings()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_speech(
    text: str,
    output_path: str,
    voice: Optional[str] = None,
    language: Optional[str] = None,
    method: Optional[str] = None,
) -> str:
    """Convert *text* to an audio file at *output_path*.

    Parameters
    ----------
    text:
        The text to speak.
    output_path:
        Destination file path (.wav or .mp3).
    voice:
        Explicit TTS voice identifier. If provided, takes precedence over
        *language* and the config default.
    language:
        BCP-47 language code (e.g. ``"en"``, ``"es"``). Used to pick the
        default voice when *voice* is not provided. Falls back to the config
        ``tts.voice`` value, then ``"en-US-GuyNeural"``.
    method:
        TTS backend to use. Defaults to config value (edge_tts).

    Returns
    -------
    str
        The absolute path to the generated audio file.
    """
    cfg = config_loader.tts()
    if method is None:
        method = cfg.get("method", "edge_tts")

    # Voice resolution: explicit > language default > config default > hardcoded
    if voice:
        resolved_voice = voice
    elif language:
        # Config language_voices override takes precedence over the hardcoded map
        cfg_voices = cfg.get("language_voices", {})
        resolved_voice = cfg_voices.get(language) or LANGUAGE_VOICES.get(language)
        if resolved_voice:
            logger.info("TTS language='%s' → voice='%s'", language, resolved_voice)
        else:
            resolved_voice = cfg.get("voice", "en-US-GuyNeural")
            logger.warning("No voice mapping for language '%s' — using '%s'.", language, resolved_voice)
    else:
        resolved_voice = cfg.get("voice", "en-US-GuyNeural")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if method == "edge_tts":
        return _edge_tts(text, output_path, resolved_voice)

    logger.warning("TTS method '%s' not supported — generating silent placeholder.", method)
    return _generate_silent_audio(output_path)


# ---------------------------------------------------------------------------
# edge_tts backend
# ---------------------------------------------------------------------------

def _edge_tts(text: str, output_path: str, voice: str) -> str:
    """Generate speech with Microsoft Edge TTS (free, no key)."""
    try:
        import edge_tts as edge_tts_module  # type: ignore[import-untyped]

        async def _run():
            communicate = edge_tts_module.Communicate(text, voice)
            await communicate.save(output_path)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # Already inside an event loop (e.g. Streamlit).
            # Run the coroutine in a separate thread with its own loop.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                # Use a lambda to ensure the coroutine is created inside the worker thread
                future = pool.submit(lambda: asyncio.run(_run()))
                future.result()
        else:
            asyncio.run(_run())
        logger.info("edge_tts audio saved → %s", output_path)
        return output_path

    except ImportError:
        logger.warning("edge_tts package not installed — falling back to silent audio.")
        return _generate_silent_audio(output_path)
    except Exception as exc:
        logger.error("edge_tts failed (%s) — falling back to silent audio.", exc)
        return _generate_silent_audio(output_path)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _generate_silent_audio(output_path: str, duration_s: float = 3.0) -> str:
    """Create a short silent audio file via ffmpeg (always available on this system)."""
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(duration_s), "-q:a", "9", "-acodec", "libmp3lame",
            output_path,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        logger.error("ffmpeg silent audio failed: %s", result.stderr.decode())
    else:
        logger.info("Silent audio placeholder saved → %s", output_path)
    return output_path
