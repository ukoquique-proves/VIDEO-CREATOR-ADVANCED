"""
Native Assembler Backend — uses the repository's local moviepy-based
assembler implementation as a concrete AssemblerBackend.
This backend is lightweight, has no external dependencies beyond moviepy, and is the default assembler implementation."""
import logging
from typing import List, Optional

from src.backends import AssemblerBackend
from src import assembler_adapter

logger = logging.getLogger(__name__)


class NativeAssemblerBackend:
    """Wrap the local moviepy assembler as an AssemblerBackend."""

    def __init__(self):
        logger.info("Initializing native MoviePy assembler backend (fully decoupled)")

    def assemble(
        self,
        audio_path: Optional[str],
        visual_files: List[str],
        title: str,
        output_dir: str,
        output_filename: str,
        background_music: Optional[str],
        width: int,
        height: int,
        duration: Optional[float] = None,
        context = None,
        visual_durations: Optional[List[float]] = None,
        **kwargs,
    ) -> Optional[str]:
        merged_config = context.merged_config if context else None
        use_logger = context.logger if context else logger
        return assembler_adapter.local_moviepy_assemble(
            audio_path=audio_path,
            visual_files=visual_files,
            output_dir=output_dir,
            output_filename=output_filename,
            width=width,
            height=height,
            duration=duration,
            background_music=background_music,
            merged_config=merged_config,
            log=use_logger,
            visual_durations=visual_durations,
        )
