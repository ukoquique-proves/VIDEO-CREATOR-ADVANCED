"""
Unit tests for the adapter modules (tts, image, subtitle, assembler).
"""

import os
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from PIL import Image

from src import tts_adapter, image_adapter, subtitle_adapter


# =========================================================================== #
# TTS Adapter
# =========================================================================== #

class TestTTSAdapter:
    def test_generate_speech_fallback(self, tmp_path):
        """The silent audio fallback should create a file without raising."""
        out = str(tmp_path / "silent.mp3")
        result = tts_adapter._generate_silent_audio(out, duration_s=1.0)
        assert result == out
        assert os.path.isfile(out)

    def test_openai_tts_called(self, tmp_path):
        """Passing method='openai' should call _openai_tts."""
        out = str(tmp_path / "openai.mp3")
        with patch.object(tts_adapter, "_openai_tts", return_value=out) as mock_openai:
            tts_adapter.generate_speech("Hello", out, method="openai")
        mock_openai.assert_called_once()

    def test_generate_speech_caching(self, tmp_path):
        """TTS should use cache on subsequent identical requests."""
        out1 = str(tmp_path / "out1.mp3")
        out2 = str(tmp_path / "out2.mp3")
        
        with patch.object(tts_adapter, "_edge_tts", return_value=out1) as mock_edge, \
             patch("src.tts_adapter.config_loader.tts", return_value={"use_cache": True, "method": "edge_tts"}):
            
            import uuid
            unique_text = f"Cache Test {uuid.uuid4()}"
            # First call creates the cache
            tts_adapter.generate_speech(unique_text, out1, voice="en-US-GuyNeural")
            mock_edge.assert_called_once()
            
            # Reset mock
            mock_edge.reset_mock()
            
            # Create a fake output from the first call so shutil.copy2 doesn't fail
            if not os.path.exists(out1):
                open(out1, "w").close()
            
            # Re-run first call properly so cache actually saves (the mock returned out1, we need out1 to exist)
            tts_adapter.generate_speech(unique_text, out1, voice="en-US-GuyNeural")
            
            mock_edge.reset_mock()
            
            # Second call should hit the cache and NOT call edge_tts
            tts_adapter.generate_speech(unique_text, out2, voice="en-US-GuyNeural")
            mock_edge.assert_not_called()
            assert os.path.isfile(out2)

    def test_unknown_method_uses_fallback(self, tmp_path):
        """An unknown TTS method should still produce a file (silent fallback)."""
        out = str(tmp_path / "unknown.mp3")
        result = tts_adapter.generate_speech("Hello", out, method="unknown_method")
        assert result == out

    def test_language_resolves_to_correct_voice(self, tmp_path):
        """Language code should map to the correct edge_tts voice."""
        out = str(tmp_path / "es.mp3")
        with patch.object(tts_adapter, "_edge_tts", return_value=out) as mock_tts:
            tts_adapter.generate_speech("Hola", out, language="es")
        mock_tts.assert_called_once_with("Hola", out, "es-AR-TomasNeural", "+0%")

    def test_explicit_voice_overrides_language(self, tmp_path):
        """An explicit voice parameter must take precedence over language."""
        out = str(tmp_path / "override.mp3")
        with patch.object(tts_adapter, "_edge_tts", return_value=out) as mock_tts:
            tts_adapter.generate_speech("Hello", out, voice="en-GB-RyanNeural", language="es")
        mock_tts.assert_called_once_with("Hello", out, "en-GB-RyanNeural", "+0%")

    def test_unknown_language_falls_back_to_config_voice(self, tmp_path):
        """An unrecognised language code should fall back to the config default voice."""
        out = str(tmp_path / "unknown_lang.mp3")
        with patch.object(tts_adapter, "_edge_tts", return_value=out) as mock_tts:
            tts_adapter.generate_speech("Hello", out, language="xx")
        # Should use the config default, not crash
        mock_tts.assert_called_once()
        _, called_voice = mock_tts.call_args[0][1], mock_tts.call_args[0][2]
        assert isinstance(called_voice, str) and len(called_voice) > 0

    def test_config_language_voices_override_hardcoded_map(self, tmp_path):
        """language_voices in config should override the hardcoded LANGUAGE_VOICES map."""
        out = str(tmp_path / "config_override.mp3")
        with patch("src.tts_adapter.config_loader.tts", return_value={
            "method": "edge_tts",
            "language_voices": {"es": "es-MX-JorgeNeural"},
        }), patch.object(tts_adapter, "_edge_tts", return_value=out) as mock_tts:
            tts_adapter.generate_speech("Hola", out, language="es")
        mock_tts.assert_called_once_with("Hola", out, "es-MX-JorgeNeural", "+0%")


# =========================================================================== #
# Image Adapter
# =========================================================================== #

class TestImageAdapter:
    def test_generate_placeholder_images(self, tmp_path):
        """Placeholder images should be created when Picsum and FootageGeneratorV2 are unavailable."""
        out_dir = str(tmp_path / "imgs")
        prompts = ["A cat", "A dog", "A bird"]
        with patch.object(image_adapter, "_picsum_batch", return_value=[]), \
             patch.object(image_adapter, "_try_footage_generator", return_value=None):
            paths = image_adapter.generate_from_prompts(prompts, out_dir)
        assert len(paths) == 3
        for p in paths:
            assert os.path.isfile(p)
            assert p.endswith(".png")

    def test_copy_provided_images(self, sample_images, tmp_path):
        """Provided images should be copied into the workspace."""
        out_dir = str(tmp_path / "copied")
        paths = image_adapter.copy_provided_images(sample_images, out_dir)
        assert len(paths) == 2
        for p in paths:
            assert os.path.isfile(p)
            assert str(tmp_path / "copied") in p

    def test_copy_skips_missing(self, tmp_path):
        """Missing source images should be skipped without raising."""
        out_dir = str(tmp_path / "out")
        paths = image_adapter.copy_provided_images(["/nonexistent/a.png"], out_dir)
        assert paths == []

    def test_modify_images_raises_not_implemented(self, sample_images):
        """modify_images should raise NotImplementedError when unimplemented."""
        with pytest.raises(NotImplementedError, match="image_modification_instructions is not yet implemented"):
            image_adapter.modify_images(sample_images, "brighten everything")

    def test_engine_pollinations_skips_picsum(self, tmp_path):
        """Passing engine='pollinations' should skip Picsum and use the requested provider."""
        out_dir = str(tmp_path / "imgs")
        with patch.object(image_adapter, "_picsum_batch", return_value=["fake.jpg"]) as mock_picsum, \
             patch.object(image_adapter, "_try_footage_generator", return_value=["lingo.png"]) as mock_lingo:
            paths = image_adapter.generate_from_prompts(["test"], out_dir, engine="pollinations")
            
        mock_picsum.assert_not_called()
        mock_lingo.assert_called_once()
        assert paths == ["lingo.png"]

    def test_engine_picsum_forces_picsum(self, tmp_path):
        """Passing engine='picsum' should force Picsum when explicitly requested."""
        out_dir = str(tmp_path / "imgs")
        with patch.object(image_adapter, "_picsum_batch", return_value=["fake.jpg"]) as mock_picsum, \
             patch.object(image_adapter, "_try_footage_generator") as mock_lingo:
            paths = image_adapter.generate_from_prompts(["test"], out_dir, engine="picsum")
            
        mock_picsum.assert_called_once()
        mock_lingo.assert_not_called()
        assert paths == ["fake.jpg"]

    def test_config_engine_defaults_to_config_value(self, tmp_path):
        """When no engine is passed explicitly, the default config engine should be used."""
        out_dir = str(tmp_path / "imgs")
        with patch("src.image_adapter.config_loader.image", return_value={"style": "photorealistic", "aspect_ratio": "9:16", "engine": "cloudflare"}), \
             patch("src.image_adapter.ensure_lingo_on_path", return_value=None), \
             patch("src.image_adapter._try_footage_generator", return_value=["cloudflare.png"]) as mock_try:
            paths = image_adapter.generate_from_prompts(["test"], out_dir)

        mock_try.assert_called_once()
        positional_args, _ = mock_try.call_args
        assert positional_args[4] == "cloudflare"
        assert paths == ["cloudflare.png"]


# =========================================================================== #
# Subtitle Adapter
# =========================================================================== #

class TestSubtitleAdapter:
    def test_basic_segmentation(self):
        """Should split text into timed segments."""
        text = "Hello world. This is a sentence with several words to test chunking."
        segments = subtitle_adapter.generate_subtitle_segments(text)
        assert len(segments) > 0
        for seg in segments:
            assert "text" in seg
            assert "start" in seg
            assert "end" in seg
            assert seg["end"] > seg["start"]

    def test_empty_text(self):
        """Empty text should produce no segments."""
        segments = subtitle_adapter.generate_subtitle_segments("")
        assert segments == []

    def test_total_duration_scaling(self):
        """Segments should be scaled to fit the given total duration."""
        text = "One two three four five six seven eight nine ten."
        segments = subtitle_adapter.generate_subtitle_segments(text, total_duration=10.0)
        last = segments[-1]
        assert abs(last["end"] - 10.0) < 0.1

    def test_long_text_chunked(self):
        """Long text should be split into multiple chunks."""
        text = " ".join([f"word{i}" for i in range(50)])
        segments = subtitle_adapter.generate_subtitle_segments(text, max_words_per_chunk=8)
        assert len(segments) >= 6  # 50 words / 8 per chunk ≈ 7
        for seg in segments:
            word_count = len(seg["text"].split())
            assert word_count <= 10  # some tolerance for sentence-based splitting

    def test_no_empty_segments_from_trailing_punctuation(self):
        """Text ending with punctuation + whitespace must not produce empty segments."""
        for text in ["Hello world. ", "One. Two. Three. ", "Done!\n"]:
            segments = subtitle_adapter.generate_subtitle_segments(text)
            for seg in segments:
                assert seg["text"].strip() != "", f"Empty segment from input {text!r}"

# =========================================================================== #
# Assembler Adapter — integration (mocked backends)
# =========================================================================== #

class TestAssemblerAdapter:
    def test_backend_assemble_called(self, tmp_path):
        """Backend.assemble should be called with audio, visuals, and metadata."""
        from src import assembler_adapter

        fake_video = str(tmp_path / "raw.mp4")
        open(fake_video, "w").close()

        mock_backend = MagicMock()
        mock_backend.assemble.return_value = fake_video

        result = assembler_adapter.assemble_video(
            audio_path="fake.mp3",
            visual_files=["fake.png"],
            output_dir=str(tmp_path),
            title="my_video",
            backend=mock_backend,
        )

        mock_backend.assemble.assert_called_once()
        assert result == fake_video

    def test_backend_does_not_receive_subtitle_kwargs(self, tmp_path):
        """Backend.assemble must never receive segments or subtitles_enabled."""
        from src import assembler_adapter

        fake_video = str(tmp_path / "lingo.mp4")
        open(fake_video, "w").close()

        mock_backend = MagicMock()
        mock_backend.assemble.return_value = fake_video

        assembler_adapter.assemble_video(
            audio_path="fake.mp3",
            visual_files=["fake.png"],
            output_dir=str(tmp_path),
            title="no_captions_test",
            backend=mock_backend,
        )

        _, kwargs = mock_backend.assemble.call_args
        assert "subtitles_enabled" not in kwargs
        assert "segments" not in kwargs

    def test_local_fallback_used_when_lingo_unavailable(self, tmp_path):
        """When the backend returns None, _local_moviepy_assemble must be called."""
        from src import assembler_adapter

        fake_video = str(tmp_path / "local.mp4")
        open(fake_video, "w").close()

        mock_backend = MagicMock()
        mock_backend.assemble.return_value = None

        with patch.object(assembler_adapter, "_local_moviepy_assemble", return_value=fake_video) as mock_local:
            result = assembler_adapter.assemble_video(
                audio_path="fake.mp3",
                visual_files=["fake.png"],
                output_dir=str(tmp_path),
                backend=mock_backend,
            )

        mock_local.assert_called_once()
        assert result == fake_video

    def test_background_music_requested_without_lingo_uses_local_fallback(self, tmp_path):
        """Requested background music should fall back to local moviepy assembly."""
        from src import assembler_adapter

        mock_backend = MagicMock()
        mock_backend.assemble.return_value = None

        fake_video = str(tmp_path / "local_with_music.mp4")
        open(fake_video, "w").close()

        with patch.object(assembler_adapter, "_local_moviepy_assemble", return_value=fake_video) as mock_local:
            result = assembler_adapter.assemble_video(
                audio_path="fake.mp3",
                visual_files=["fake.png"],
                output_dir=str(tmp_path),
                backend=mock_backend,
                background_music="music.mp3",
            )

        mock_local.assert_called_once()
        assert result == fake_video

    def test_moviepy_import_error_raises_runtime_error(self, tmp_path):
        """A broken moviepy install should raise RuntimeError with a clear message."""
        import sys
        import types
        from src import assembler_adapter

        class _BrokenMoviepy(types.ModuleType):
            def __getattr__(self, name):
                raise ImportError(f"moviepy is broken: {name}")

        mock_backend = MagicMock()
        mock_backend.assemble.return_value = None

        with patch.dict(sys.modules, {"moviepy": _BrokenMoviepy("moviepy"), "moviepy.video.fx": _BrokenMoviepy("moviepy.video.fx")}):
            with pytest.raises(RuntimeError, match="moviepy is required"):
                assembler_adapter.assemble_video(
                    audio_path="fake.mp3",
                    visual_files=["fake.png"],
                    output_dir=str(tmp_path),
                    backend=mock_backend,
                )

