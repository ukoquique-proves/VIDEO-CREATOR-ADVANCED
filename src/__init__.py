"""
VideoCreation — Configurable video generation pipeline.

Accepts speech text, visual assets, and styling options to produce a complete video file.
Lingo_PERSONAS is an optional integration used for AI image generation and video assembly;
TTS runs independently via edge_tts with no Lingo dependency.
"""

from src.schema import VideoConfiguration, VisualAssetType, VisualAssetConfig, OutputFormat

__all__ = [
    "VideoConfiguration",
    "VisualAssetType",
    "VisualAssetConfig",
    "OutputFormat",
]
