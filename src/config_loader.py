"""
Config loader — reads config/default_config.yaml and exposes typed settings.
"""

import copy
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "default_config.yaml"
# Cache is now keyed by resolved config path string
_cache: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def load(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Return the parsed config dict (cached after first load).
    
    Args:
        path: Optional path to config file. If not provided, checks
              CONFIG_PATH env var, then falls back to default_config.yaml.
    """
    with _lock:
        # Determine config path
        if path is None:
            config_path_env = os.environ.get("CONFIG_PATH")
            if config_path_env:
                config_path = Path(config_path_env).resolve()
            else:
                config_path = _DEFAULT_CONFIG_PATH
        else:
            config_path = Path(path).resolve()
        config_path_str = str(config_path)
        
        # Check if we already have this config cached
        if config_path_str not in _cache:
            _new: Dict[str, Any] = {}
            try:
                with open(config_path, "r") as f:
                    data = yaml.safe_load(f)
                    if data:
                        _new.update(data)
            except FileNotFoundError:
                raise RuntimeError(
                    f"VideoCreation config not found: {config_path}\n"
                    f"Ensure config file exists at the specified path, or set CONFIG_PATH env var."
                ) from None
            _cache[config_path_str] = _new
        
        return copy.deepcopy(_cache[config_path_str])


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


def pollinations() -> Dict[str, Any]:
    return load().get("pollinations", {})
