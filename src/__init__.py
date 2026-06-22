"""
VideoCreation — Configurable video generation pipeline.

Accepts speech text, visual assets, and styling options to produce a complete video file.
All core pipeline features are fully decoupled, lightweight, and implemented natively.
"""

from src.schema import VideoConfiguration, VisualAssetType, VisualAssetConfig, OutputFormat

__all__ = [
    "VideoConfiguration",
    "VisualAssetType",
    "VisualAssetConfig",
    "OutputFormat",
]
