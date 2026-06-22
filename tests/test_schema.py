"""
Tests for the Pydantic schema models.
"""

import pytest
from src.schema import (
    VideoConfiguration,
    VisualAssetConfig,
    VisualAssetType,
    OutputFormat,
    Language,
    TTSBackend,
    ImageEngine,
)


class TestOutputFormat:
    def test_enum_values(self):
        assert OutputFormat.MP4.value == "mp4"
        assert OutputFormat.WEBM.value == "webm"
        assert OutputFormat.MOV.value == "mov"
        assert OutputFormat.AVI.value == "avi"


class TestLanguage:
    def test_enum_values(self):
        assert Language.ENGLISH.value == "en"
        assert Language.SPANISH.value == "es"
        assert Language.CHINESE.value == "zh"
        assert Language.FRENCH.value == "fr"
        assert Language.GERMAN.value == "de"
        assert Language.PORTUGUESE.value == "pt"


class TestVisualAssetConfig:
    def test_image_sequence(self):
        cfg = VisualAssetConfig(
            asset_type=VisualAssetType.IMAGE_SEQUENCE,
            images=["/path/a.png", "/path/b.png"],
        )
        assert cfg.asset_type == VisualAssetType.IMAGE_SEQUENCE
        assert len(cfg.images) == 2
        assert cfg.prompts is None

    def test_text_prompts(self):
        cfg = VisualAssetConfig(
            asset_type=VisualAssetType.TEXT_PROMPTS,
            prompts=["A sunny beach", "A dark forest"],
        )
        assert cfg.asset_type == VisualAssetType.TEXT_PROMPTS
        assert len(cfg.prompts) == 2
        assert cfg.images is None

    def test_media_sequence(self):
        cfg = VisualAssetConfig(
            asset_type=VisualAssetType.MEDIA_SEQUENCE,
            images=["a.png", "b.mp4"],
        )
        assert cfg.asset_type == VisualAssetType.MEDIA_SEQUENCE
        assert len(cfg.images) == 2


class TestVideoConfiguration:
    def test_minimal_valid(self):
        cfg = VideoConfiguration(
            title="Test",
            speech_content="Hello world",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.IMAGE_SEQUENCE,
                images=["a.png"],
            ),
        )
        assert cfg.title == "Test"
        assert cfg.output_format == OutputFormat.MP4
        assert cfg.subtitles_enabled is False
        assert cfg.length_seconds is None
        assert cfg.background_music is None
        assert cfg.language == Language.ENGLISH  # default
        assert cfg.tts_backend is None
        assert cfg.image_engine is None
        assert cfg.image_style is None

    def test_all_fields(self):
        cfg = VideoConfiguration(
            title="Full Test",
            length_seconds=60,
            speech_content="Some speech content here.",
            background_music="/music/bg.mp3",
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType.TEXT_PROMPTS,
                prompts=["prompt1"],
            ),
            image_modification_instructions="Make it brighter",
            subtitles_enabled=True,
            output_format=OutputFormat.WEBM,
        )
        assert cfg.length_seconds == 60
        assert cfg.subtitles_enabled is True
        assert cfg.output_format == OutputFormat.WEBM
        assert cfg.image_modification_instructions == "Make it brighter"

    def test_language_field(self):
        cfg = VideoConfiguration(
            title="Spanish Video",
            speech_content="Hola mundo",
            visual_assets=VisualAssetConfig(asset_type=VisualAssetType.IMAGE_SEQUENCE),
            language=Language.SPANISH,
        )
        assert cfg.language == Language.SPANISH
        assert cfg.language.value == "es"

    def test_language_accepts_string(self):
        """Schema should coerce the string 'es' to Language.SPANISH."""
        cfg = VideoConfiguration(
            title="Spanish Video",
            speech_content="Hola mundo",
            visual_assets=VisualAssetConfig(asset_type=VisualAssetType.IMAGE_SEQUENCE),
            language="es",
        )
        assert cfg.language == Language.SPANISH

    def test_per_video_provider_fields(self):
        cfg = VideoConfiguration(
            title="Override Test",
            speech_content="Testing overrides.",
            visual_assets=VisualAssetConfig(asset_type=VisualAssetType.IMAGE_SEQUENCE),
            tts_backend=TTSBackend.EDGE_TTS,
            image_engine=ImageEngine.POLLINATIONS,
            image_style="cinematic",
        )
        assert cfg.tts_backend == TTSBackend.EDGE_TTS
        assert cfg.image_engine == ImageEngine.POLLINATIONS
        assert cfg.image_style == "cinematic"

    def test_missing_required_field_raises(self):
        with pytest.raises(Exception):
            VideoConfiguration(
                speech_content="oops",
                visual_assets=VisualAssetConfig(
                    asset_type=VisualAssetType.IMAGE_SEQUENCE,
                ),
            )

    def test_invalid_output_format(self):
        with pytest.raises(Exception):
            VideoConfiguration(
                title="Bad",
                speech_content="x",
                visual_assets=VisualAssetConfig(
                    asset_type=VisualAssetType.IMAGE_SEQUENCE,
                ),
                output_format="gif",
            )

    def test_invalid_language(self):
        with pytest.raises(Exception):
            VideoConfiguration(
                title="Bad",
                speech_content="x",
                visual_assets=VisualAssetConfig(
                    asset_type=VisualAssetType.IMAGE_SEQUENCE,
                ),
                language="klingon",
            )
