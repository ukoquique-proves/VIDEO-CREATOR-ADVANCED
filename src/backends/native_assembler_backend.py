"""
Native Assembler Backend — uses the repository's local moviepy-based
assembler implementation as a concrete AssemblerBackend.

This backend is lightweight and has no external Lingo dependency; it is
intended to be the default when Lingo_PERSONAS is not installed.
"""
import logging
from typing import List, Optional

from src.backends import AssemblerBackend
from src import assembler_adapter

logger = logging.getLogger(__name__)


class NativeAssemblerBackend:
    """Wrap the local moviepy assembler as an AssemblerBackend."""

    def assemble(
        self,
        audio_path: str,
        visual_files: List[str],
        title: str,
        output_dir: str,
        output_filename: str,
        background_music: Optional[str],
        width: int,
        height: int,
    ) -> Optional[str]:
        try:
            return assembler_adapter._local_moviepy_assemble(
                audio_path=audio_path,
                visual_files=visual_files,
                output_dir=output_dir,
                output_filename=output_filename,
                width=width,
                height=height,
                duration=None,
                background_music=background_music,
            )
        except Exception as exc:
            logger.warning("Native assembler failed: %s", exc)
            return None
