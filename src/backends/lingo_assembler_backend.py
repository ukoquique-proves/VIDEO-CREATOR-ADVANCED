"""
Lingo Assembler Backend — encapsulates all Lingo_PERSONAS VideoAssembler
interaction behind the ``AssemblerBackend`` protocol.

``assembler_adapter`` calls this class; it has no direct knowledge of Lingo's
API surface.  Swapping or mocking Lingo only requires replacing this class.
"""

import logging
from typing import Dict, List, Optional

from src.lingo_utils import ensure_lingo_on_path
from src import config_loader

logger = logging.getLogger(__name__)


class LingoAssemblerBackend:
    """Wraps Lingo_PERSONAS VideoAssembler behind the AssemblerBackend interface."""

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
        """Attempt assembly via Lingo_PERSONAS VideoAssembler.

        Captions are always disabled (``add_captions=False``) because Lingo's
        renderer clips descenders.  Subtitle burn-in is handled separately by
        ``subtitle_renderer``.

        Returns the output path on success, or ``None`` if Lingo is unavailable.
        """
        try:
            ensure_lingo_on_path()
            from shorts_creator.video_assembler import VideoAssembler, VideoConfig  # type: ignore[import-untyped]

            vcfg = config_loader.video()
            config = VideoConfig(
                width=width,
                height=height,
                fps=vcfg.get("fps", 30),
                bitrate=vcfg.get("bitrate", "8000k"),
            )
            assembler = VideoAssembler(output_dir=output_dir, config=config)

            script_data: Dict = {"title": title, "segments": []}
            result = assembler.assemble_video(
                script_data=script_data,
                audio_files=[audio_path],
                visual_files=visual_files,
                background_music=background_music,
                output_filename=output_filename,
                add_captions=False,  # subtitle rendering is our responsibility
            )
            logger.info("Lingo VideoAssembler → %s", result)
            return result

        except ImportError as exc:
            logger.warning("Lingo VideoAssembler unavailable (%s) — returning None.", exc)
            return None
        except Exception as exc:
            logger.error("Lingo VideoAssembler failed (%s) — returning None.", exc)
            return None
