from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import logging


class OutputFormat(str, Enum):
    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"
    WEBM = "webm"


class VisualAssetType(str, Enum):
    IMAGE_SEQUENCE = "image_sequence"
    TEXT_PROMPTS = "text_prompts"
    MEDIA_SEQUENCE = "media_sequence"


class TTSBackend(str, Enum):
    EDGE_TTS = "edge_tts"
    KOKORO = "kokoro"
    AZURE = "azure"
    OPENAI = "openai"
    FISH_TTS = "fish_tts"


class Language(str, Enum):
    ENGLISH = "en"
    SPANISH = "es"
    CHINESE = "zh"
    FRENCH = "fr"
    GERMAN = "de"
    PORTUGUESE = "pt"


class Orientation(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


class ImageEngine(str, Enum):
    POLLINATIONS = "pollinations"
    HUGGINGFACE  = "huggingface"
    CLOUDFLARE   = "cloudflare"
    SILICONFLOW  = "siliconflow"
    PICSUM       = "picsum"


class VisualAssetConfig(BaseModel):
    asset_type: VisualAssetType
    images: Optional[List[str]] = Field(
        default=None,
        description="Paths to local image files if using IMAGE_SEQUENCE",
    )
    prompts: Optional[List[str]] = Field(
        default=None,
        description="Text prompts for AI image generation if using TEXT_PROMPTS",
    )
    prompt_speeches: Optional[List[str]] = Field(
        default=None,
        description=(
            "Per-scene speech text, one entry per prompt/image. "
            "When provided, each visual is shown for the duration proportional "
            "to its speech word-count, keeping audio and images in sync. "
            "The combined text should match speech_content exactly."
        ),
    )


class VideoConfiguration(BaseModel):
    title: str = Field(..., description="The title of the video")
    length_seconds: Optional[float] = Field(
        default=None, description="Desired video length in seconds"
    )
    speech_content: Optional[str] = Field(
        default=None, 
        description="Plain text to be converted to audio (required if speech_audio not provided)"
    )
    speech_audio: Optional[str] = Field(
        default=None, 
        description="Path to pre-made speech audio file (skips TTS if provided)"
    )
    background_music: Optional[str] = Field(
        default=None, description="Path to background music audio file",
    )
    visual_assets: VisualAssetConfig = Field(..., description="Visual assets configuration")
    image_modification_instructions: Optional[str] = Field(
        default=None, description="Optional AI instructions to modify images"
    )
    subtitles_enabled: bool = Field(
        default=False, description="Toggle to burn subtitles onto the video"
    )

    @field_validator("image_modification_instructions")
    def reject_unsupported_image_modification(cls, value):
        if value is not None:
            raise ValueError(
                "image_modification_instructions is reserved for future use and is not supported yet. "
                "Remove this field from your configuration until the feature is implemented."
            )
        return value
    output_format: OutputFormat = Field(
        default=OutputFormat.MP4, description="Output video format"
    )
    orientation: Orientation = Field(
        default=Orientation.VERTICAL, description="Video orientation (vertical or horizontal)"
    )
    # Per-video provider overrides — take precedence over default_config.yaml
    language: Language = Field(
        default=Language.ENGLISH,
        description="Language for TTS voice selection",
    )
    tts_backend: Optional[TTSBackend] = Field(
        default=None,
        description="TTS backend to use for this video (overrides config default)",
    )
    image_engine: Optional[ImageEngine] = Field(
        default=None,
        description="Image generation engine for this video (overrides config default)",
    )
    image_style: Optional[str] = Field(
        default=None,
        description="Image style preset for this video, e.g. 'cinematic' (overrides config default)",
    )
    tts_voice: Optional[str] = Field(
        default=None,
        description="TTS voice for this video (overrides config and language defaults)",
    )
    tts_rate: Optional[str] = Field(
        default=None,
        description="Speaking rate for this video, e.g. '-10%' (overrides config default)",
    )
    save_to_source_folder: bool = Field(
        default=False,
        description="When True and using local images/videos, save output video to the source folder instead of the default output directory",
    )


@dataclass
class VideoContext:
    config: VideoConfiguration
    output_dir: Path
    workspace: Path
    
    width: int
    height: int
    
    # Merged config (defaults from default_config.yaml + overrides from VideoConfiguration)
    merged_config: Dict[str, Any]
    
    logger: logging.Logger
    
    duration: Optional[float] = None
