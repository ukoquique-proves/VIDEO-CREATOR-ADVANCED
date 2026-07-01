"""
TTSService — handles TTS audio generation using tts_adapter.
"""

import logging
from pathlib import Path
from typing import Optional

from src.schema import VideoConfiguration, VideoContext
from src import tts_adapter


logger = logging.getLogger(__name__)


class TTSService:
    """Service for generating TTS audio."""

    def __init__(self, tts_callable=None):
        self._tts_callable = tts_callable

    def run_tts_audio(self, config: VideoConfiguration, workspace: Path, context: Optional[VideoContext] = None) -> str:
        """Generate TTS audio from speech content and return the path."""
        audio_path = str(workspace / "speech.mp3")
        logger.info("[1/4] Generating TTS audio …")

        if self._tts_callable is not None:
            self._tts_callable(
                text=config.speech_content,
                output_path=audio_path,
                language=config.language.value,
                method=config.tts_backend.value if config.tts_backend else None,
                rate=config.tts_rate,
                voice=config.tts_voice,
            )
        else:
            if context is not None:
                tts_adapter.generate_speech(
                    context=context,
                    text=config.speech_content,
                    output_path=audio_path,
                    language=config.language.value,
                    method=config.tts_backend.value if config.tts_backend else None,
                    rate=config.tts_rate,
                    voice=config.tts_voice,
                )
            else:
                tts_adapter.generate_speech(
                    text=config.speech_content,
                    output_path=audio_path,
                    language=config.language.value,
                    method=config.tts_backend.value if config.tts_backend else None,
                    rate=config.tts_rate,
                    voice=config.tts_voice,
                )
        return audio_path
