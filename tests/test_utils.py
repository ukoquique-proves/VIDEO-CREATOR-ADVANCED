"""
Tests for shared utilities.
"""

from src.utils import is_video_file


def test_is_video_file():
    assert is_video_file("video.mp4") is True
    assert is_video_file("video.MP4") is True
    assert is_video_file("clip.mov") is True
    assert is_video_file("image.png") is False
    assert is_video_file("image.jpg") is False
    assert is_video_file("readme.txt") is False
    assert is_video_file("no_extension") is False
