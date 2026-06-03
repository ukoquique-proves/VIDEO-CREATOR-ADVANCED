"""
Config loader — reads config/default_config.yaml and exposes typed settings.
"""

from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default_config.yaml"
_cache: Dict[str, Any] = {}


def load() -> Dict[str, Any]:
    """Return the parsed config dict (cached after first load)."""
    if not _cache:
        try:
            with open(_CONFIG_PATH, "r") as f:
                _cache.update(yaml.safe_load(f))
        except FileNotFoundError:
            raise RuntimeError(
                f"VideoCreation config not found: {_CONFIG_PATH}\n"
                "Ensure 'config/default_config.yaml' exists at the project root."
            ) from None
    return _cache


def _clear_cache() -> None:
    """Clear the config cache. Intended for use in tests only."""
    _cache.clear()


def tts() -> Dict[str, Any]:
    return load().get("tts", {})


def image() -> Dict[str, Any]:
    return load().get("image", {})


def video() -> Dict[str, Any]:
    return load().get("video", {})


def subtitles() -> Dict[str, Any]:
    return load().get("subtitles", {})


def lingo() -> Dict[str, Any]:
    return load().get("lingo", {})


def pollinations() -> Dict[str, Any]:
    return load().get("pollinations", {})
