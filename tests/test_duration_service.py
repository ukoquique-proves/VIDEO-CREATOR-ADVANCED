"""
Tests for duration_service.py
"""
import logging
from unittest.mock import patch, MagicMock

import pytest

from src.duration_service import probe_audio_duration, resolve_total_duration


def test_probe_audio_duration_with_sample_audio(sample_audio):
    duration = probe_audio_duration(sample_audio)
    assert isinstance(duration, float)
    assert 1.9 <= duration <= 2.1


def test_resolve_total_duration_explicit_seconds():
    explicit_duration = 10.5
    result = resolve_total_duration(explicit_duration, "/does/not/exist.mp3")
    assert result == explicit_duration


def test_resolve_total_duration_probe_falls_back_to_moviepy(sample_audio):
    # Mock ffprobe to fail
    with patch("src.duration_service.subprocess.run", side_effect=Exception("ffprobe failed")):
        duration = resolve_total_duration(None, sample_audio)
        assert isinstance(duration, float)
        assert 1.9 <= duration <= 2.1


def test_resolve_total_duration_probe_and_moviepy_fail():
    # Mock both ffprobe and moviepy to fail
    def mock_import(name, *args, **kwargs):
        if name == "moviepy":
            raise Exception("moviepy import failed")
        return __import__(name, *args, **kwargs)
    
    with patch("src.duration_service.subprocess.run", side_effect=Exception("ffprobe failed")), \
         patch("builtins.__import__", side_effect=mock_import):
        duration = resolve_total_duration(None, "/does/not/exist.mp3")
        assert duration is None


def test_resolve_total_duration_uses_provided_logger():
    test_logger = logging.getLogger("test_logger")
    test_logger.debug = MagicMock()
    
    resolve_total_duration(5.0, "/does/not/exist.mp3", logger_instance=test_logger)
    
    test_logger.debug.assert_called_once_with("Using explicit duration: %.2fs", 5.0)
