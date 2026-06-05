"""
Shorts Creator Module - AI-powered short-form video generation

This module extends VideoLingo for automated content creation:
- AI script writing
- TTS voiceover generation
- Stock footage/image generation
- TikTok/Reels style video assembly

New in v2: Decoupled image provider architecture with automatic failover
between multiple free AI providers (Pollinations, HuggingFace FLUX/SD).
"""

from .script_generator import ScriptGenerator
from .footage_generator import FootageGenerator
from .video_assembler import VideoAssembler

# New v2 provider architecture with automatic failover
from .footage_generator_v2 import FootageGeneratorV2, generate_image_with_failover
from .image_providers import (
    ProviderManager,
    ProviderResult,
    ProviderStatus,
    PollinationsProvider,
    HuggingFaceFluxProvider,
    HuggingFaceSDProvider,
    create_default_manager
)
from .cleanup import (
    cleanup_shorts_output,
    auto_cleanup_before_creation,
    aggressive_cleanup,
    print_cleanup_report
)

__all__ = [
    'ScriptGenerator', 
    'FootageGenerator', 
    'VideoAssembler',
    # v2 exports
    'FootageGeneratorV2',
    'generate_image_with_failover',
    'ProviderManager',
    'ProviderResult',
    'ProviderStatus',
    'PollinationsProvider',
    'HuggingFaceFluxProvider',
    'HuggingFaceSDProvider',
    'create_default_manager',
    # cleanup exports
    'cleanup_shorts_output',
    'auto_cleanup_before_creation',
    'aggressive_cleanup',
    'print_cleanup_report'
]
