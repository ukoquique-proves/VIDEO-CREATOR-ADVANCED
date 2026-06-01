"""
Assembler backend protocol — stable interface between assembler_adapter
and any concrete backend (Lingo, local moviepy, future alternatives).
"""

from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class AssemblerBackend(Protocol):
    """Minimal interface every assembler backend must satisfy."""

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
        """Assemble audio + visuals into a video file.

        Returns the output path on success, or ``None`` if the backend is
        unavailable so the caller can fall through to the next option.
        """
        ...
