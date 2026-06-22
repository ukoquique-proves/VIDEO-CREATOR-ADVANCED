"""
Config loader — reads config/default_config.yaml and exposes typed settings.
"""

import copy
import threading
from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default_config.yaml"
_cache: Dict[str, Any] = {}
_lock = threading.Lock()


def load() -> Dict[str, Any]:
    """Return the parsed config dict (cached after first load)."""
    with _lock:
        if not _cache:
            _new: Dict[str, Any] = {}
            try:
                with open(_CONFIG_PATH, "r") as f:
                    data = yaml.safe_load(f)
                    if data:
                        _new.update(data)
            except FileNotFoundError:
                raise RuntimeError(
                    f"VideoCreation config not found: {_CONFIG_PATH}\n"
                    "Ensure 'config/default_config.yaml' exists at the project root."
                ) from None
            _cache.update(_new)
        return copy.deepcopy(_cache)


def _clear_cache() -> None:
    """Clear the config cache. Intended for use in tests only."""
    with _lock:
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
