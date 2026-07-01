"""
TTS Adapter — Text-to-Speech bridge.

Supports:
  - edge_tts (free, no API key)
  - kokoro (free, local, no API key — higher naturalness than edge_tts)
  - openai (requires API key)
  - ffmpeg silent-audio fallback for testing / offline use
"""

import asyncio
import concurrent.futures
import hashlib
import logging
import shutil
import subprocess
import warnings
from pathlib import Path
from typing import Optional, List
from src import config_loader
from src.schema import Language

logger = logging.getLogger(__name__)

# Default edge_tts voice per language code.
# Full list: https://speech.microsoft.com/portal/voicegallery
LANGUAGE_VOICES: dict = {
    Language.ENGLISH.value: "en-US-BrianNeural",
    Language.SPANISH.value: "es-MX-JorgeNeural",
    Language.CHINESE.value: "zh-CN-YunxiNeural",
    Language.FRENCH.value: "fr-FR-HenriNeural",
    Language.GERMAN.value: "de-DE-ConradNeural",
    Language.PORTUGUESE.value: "pt-BR-AntonioNeural",
}

KOKORO_LANGUAGE_VOICES: dict = {
    Language.ENGLISH.value: ("a", "af_heart"),
    Language.SPANISH.value: ("e", "ef_dora"),
    Language.CHINESE.value: ("z", "zf_xiaobei"),
    Language.FRENCH.value: ("f", "ff_siwis"),
    Language.GERMAN.value: ("a", "af_heart"),
    Language.PORTUGUESE.value: ("p", "pf_dora"),
}

_kokoro_pipelines: dict = {}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_voice_mappings():
    """Ensure all languages defined in schema have a default voice mapping."""
    missing = []
    for lang in Language:
        if lang.value not in LANGUAGE_VOICES:
            missing.append(lang.value)
    if missing:
        # Fail fast so CI and development environments notice missing mappings.
        raise RuntimeError(f"Missing TTS voice mappings for languages: {missing}")

# Validate on module import
validate_voice_mappings()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

from src.schema import VideoContext

def generate_speech(
    *args,
    **kwargs
) -> str:
    """Convert text to an audio file at output_path.

    The preferred call style is keyword-based, for example:
    generate_speech(text="Hello", output_path="out.mp3", context=context)

    Legacy positional calls that pass a VideoContext as the first argument are
    still supported for compatibility, but they emit a DeprecationWarning.
    """
    context = kwargs.pop("context", None) or kwargs.pop("video_context", None)

    if context is None and args and isinstance(args[0], VideoContext):
        warnings.warn(
            "Passing VideoContext positionally to generate_speech() is deprecated; use context=... instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        context = args[0]

    if context is not None:
        text = args[1] if len(args) > 1 else kwargs.pop("text", None)
        output_path = args[2] if len(args) > 2 else kwargs.pop("output_path", None)
        voice = args[3] if len(args) > 3 else kwargs.pop("voice", None)
        language = args[4] if len(args) > 4 else kwargs.pop("language", None)
        method = args[5] if len(args) > 5 else kwargs.pop("method", None)
        rate = args[6] if len(args) > 6 else kwargs.pop("rate", None)

        cfg = context.merged_config.get("tts", {})
        use_logger = context.logger
    else:
        text = args[0] if len(args) > 0 else kwargs.pop("text", None)
        output_path = args[1] if len(args) > 1 else kwargs.pop("output_path", None)
        voice = args[2] if len(args) > 2 else kwargs.pop("voice", None)
        language = args[3] if len(args) > 3 else kwargs.pop("language", None)
        method = args[4] if len(args) > 4 else kwargs.pop("method", None)
        rate = args[5] if len(args) > 5 else kwargs.pop("rate", None)

        cfg = config_loader.tts()
        use_logger = logger
        
    if method is None:
        method = cfg.get("method", "edge_tts")

    if rate is None:
        rate = cfg.get("rate", "+0%")

    if method == "kokoro":
        if voice:
            resolved_voice = voice
        elif language:
            lang_entry = KOKORO_LANGUAGE_VOICES.get(language, KOKORO_LANGUAGE_VOICES[Language.ENGLISH.value])
            _, resolved_voice = lang_entry
            use_logger.info("Kokoro language='%s' → voice='%s'", language, resolved_voice)
        else:
            resolved_voice = cfg.get("voice", "af_heart")
    elif voice:
        resolved_voice = voice
    elif language:
        cfg_voices = cfg.get("language_voices", {})
        resolved_voice = cfg_voices.get(language) or LANGUAGE_VOICES.get(language)
        if resolved_voice:
            use_logger.info("TTS language='%s' → voice='%s'", language, resolved_voice)
        else:
            resolved_voice = cfg.get("voice", "en-US-GuyNeural")
            use_logger.warning("No voice mapping for language '%s' — using '%s'.", language, resolved_voice)
    else:
        resolved_voice = cfg.get("voice", "en-US-GuyNeural")

    use_cache = cfg.get("use_cache", True)
    if use_cache:
        project_root = Path(__file__).resolve().parents[1]
        cache_dir = project_root / ".cache" / "tts"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        key_data = f"{text}|{method}|{resolved_voice}|{rate}".encode("utf-8")
        file_hash = hashlib.md5(key_data).hexdigest()
        ext = Path(output_path).suffix or ".mp3"
        cache_file = cache_dir / f"{file_hash}{ext}"
        
        if cache_file.exists():
            try:
                if cache_file.stat().st_size == 0:
                    use_logger.warning(
                        "TTS cache file is zero bytes (corrupt): %s — removing and regenerating.", cache_file
                    )
                    cache_file.unlink()
                else:
                    use_logger.info("TTS cache hit for '%s...' voice='%s' rate='%s'.", text[:20], resolved_voice, rate)
                    try:
                        shutil.copy2(cache_file, output_path)
                        return output_path
                    except FileNotFoundError:
                        use_logger.warning("TTS cache file disappeared mid-read (race): %s — regenerating.", cache_file)
            except FileNotFoundError:
                pass

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    res = None
    if method == "edge_tts":
        res = _edge_tts(text, output_path, resolved_voice, rate, use_logger)
    elif method == "kokoro":
        res = _kokoro_tts(text, output_path, resolved_voice, language or "en", use_logger)
    elif method == "espeak":
        res = _espeak_tts(text, output_path, resolved_voice, language or "en", use_logger)
    elif method == "openai":
        res = _openai_tts(text, output_path, resolved_voice, use_logger)
    else:
        use_logger.warning("TTS method '%s' not supported — generating silent placeholder.", method)
        res = _generate_silent_audio(output_path, use_logger)

    if use_cache and res and Path(res).exists():
        try:
            size = Path(res).stat().st_size
        except Exception:
            size = 0

        if size > 0:
            shutil.copy2(res, cache_file)
            use_logger.info("TTS result cached → %s", cache_file)
        else:
            use_logger.warning(
                "TTS produced a zero-byte audio file for text starting '%s...' — skipping cache and regenerating silent fallback.",
                text[:20],
            )
            try:
                Path(res).unlink()
            except Exception:
                pass
            res = _generate_silent_audio(output_path, use_logger)
            try:
                if Path(res).stat().st_size > 0:
                    shutil.copy2(res, cache_file)
                    use_logger.info("Silent fallback cached → %s", cache_file)
            except Exception:
                pass

    return res


def _edge_tts(text: str, output_path: str, voice: str, rate: str = "+0%", log = logger) -> str:
    try:
        import edge_tts as edge_tts_module

        async def _run():
            communicate = edge_tts_module.Communicate(text, voice, rate=rate)
            await communicate.save(output_path)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: asyncio.run(_run()))
                future.result()
        else:
            asyncio.run(_run())
        log.info("edge_tts audio saved → %s", output_path)
        return output_path

    except ImportError:
        log.warning("edge_tts package not installed — falling back to silent audio.")
        return _generate_silent_audio(output_path, log)
    except Exception as exc:
        log.error("edge_tts failed (%s) — falling back to silent audio.", exc)
        return _generate_silent_audio(output_path, log)


def _generate_silent_audio(output_path: str, log = logger, duration_s: float = 3.0) -> str:
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(duration_s), "-q:a", "9", "-acodec", "libmp3lame",
            output_path,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed to generate silent audio (exit {result.returncode}): "
            f"{result.stderr.decode()}"
        )
    log.info("Silent audio placeholder saved → %s", output_path)
    return output_path


def _kokoro_fallback_to_edge_tts(text: str, output_path: str, language: str, rate: str, log = logger) -> str:
    cfg = config_loader.tts()
    cfg_voices = cfg.get("language_voices", {})
    edge_voice = cfg_voices.get(language) or LANGUAGE_VOICES.get(language)
    if not edge_voice:
        edge_voice = cfg.get("voice", "en-US-GuyNeural")
        log.warning("No voice mapping for language '%s' — using '%s'.", language, edge_voice)
    return _edge_tts(text, output_path, edge_voice, rate, log)


def _kokoro_tts(text: str, output_path: str, voice: Optional[str], language: str, log = logger) -> str:
    try:
        from kokoro import KPipeline  # type: ignore[import-untyped]
        import soundfile as sf         # type: ignore[import-untyped]
        import numpy as np
    except ImportError as exc:
        log.warning(
            "Kokoro dependencies missing (%s). Falling back to edge-tts audio generation.",
            exc,
        )
        return _kokoro_fallback_to_edge_tts(text, output_path, language, "+0%", log)

    try:
        lang_code, default_voice = KOKORO_LANGUAGE_VOICES.get(
            language,
            KOKORO_LANGUAGE_VOICES[Language.ENGLISH.value],
        )
        resolved = voice if (voice and "_" in voice) else default_voice

        if lang_code not in _kokoro_pipelines:
            log.info("Loading Kokoro pipeline for lang_code='%s'", lang_code)
            _kokoro_pipelines[lang_code] = KPipeline(lang_code=lang_code)
        pipeline = _kokoro_pipelines[lang_code]

        chunks: List = []
        for _gs, _ps, audio_chunk in pipeline(text, voice=resolved, speed=1.0):
            chunks.append(audio_chunk)

        if not chunks:
            log.warning("Kokoro produced no audio chunks — falling back to edge-tts audio generation.")
            return _kokoro_fallback_to_edge_tts(text, output_path, language, "+0%", log)

        combined = np.concatenate(chunks)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, combined, samplerate=24000)
        log.info("Kokoro audio saved → %s", output_path)
        return output_path
    except Exception as exc:
        log.error("Kokoro TTS failed: %s — falling back to edge-tts audio generation.", exc)
        return _kokoro_fallback_to_edge_tts(text, output_path, language, "+0%", log)


def _espeak_tts(text: str, output_path: str, voice: Optional[str], language: str, log = logger) -> str:
    try:
        lang_code = language or "en"
        voice_arg = None
        if voice and "_" in voice:
            voice_arg = voice
        if voice_arg is None:
            voice_arg = KOKORO_LANGUAGE_VOICES.get(lang_code, KOKORO_LANGUAGE_VOICES[Language.ENGLISH.value])[1]

        cmd = ["espeak-ng", "-w", output_path, "-v", voice_arg, text]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "espeak-ng failed")
        log.info("espeak-ng audio saved → %s", output_path)
        return output_path
    except Exception as exc:
        log.error("espeak-ng TTS failed: %s — falling back to silent audio.", exc)
        return _generate_silent_audio(output_path, log)


def _openai_tts(text: str, output_path: str, voice: str, log = logger) -> str:
    try:
        from openai import OpenAI
        client = OpenAI()
        
        valid_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
        oai_voice = voice if voice in valid_voices else "alloy"
        
        log.info("Generating OpenAI TTS with voice='%s'", oai_voice)
        response = client.audio.speech.create(
            model="tts-1",
            voice=oai_voice,
            input=text
        )
        response.write_to_file(output_path)
        return output_path
    except ImportError:
        log.error("openai package not installed. Run 'pip install openai'. Falling back to silent audio.")
        return _generate_silent_audio(output_path, log)
    except Exception as exc:
        log.error("OpenAI TTS failed: %s — falling back to silent audio.", exc)
        return _generate_silent_audio(output_path, log)


