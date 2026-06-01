"""
Shared Lingo_PERSONAS utilities.

Centralises the LINGO_ROOT path resolution and sys.path injection so
adapters don't each duplicate this logic.

Path resolution order:
  1. LINGO_ROOT environment variable
  2. lingo.root in config/default_config.yaml
  3. Hardcoded default (logs a warning so it's visible)
"""

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_HARDCODED_DEFAULT = "/root/a_VIDEO_GENERATION/VIDEO_PERSONAS/Lingo_PERSONAS"


def get_lingo_root() -> Path:
    """Resolve the Lingo_PERSONAS root directory.

    Checks, in order:
    1. ``LINGO_ROOT`` environment variable
    2. ``lingo.root`` in ``config/default_config.yaml``
    3. Hardcoded default (emits a warning)
    """
    # 1. Environment variable
    env_val = os.environ.get("LINGO_ROOT")
    if env_val:
        return Path(env_val)

    # 2. Config file
    try:
        from src import config_loader
        cfg_val = config_loader.lingo().get("root")
        if cfg_val:
            return Path(cfg_val)
    except Exception:
        pass  # config unavailable — fall through to default

    # 3. Hardcoded default
    logger.warning(
        "LINGO_ROOT not set via environment variable or config — "
        "using hardcoded default: %s. "
        "Set the LINGO_ROOT environment variable to override.",
        _HARDCODED_DEFAULT,
    )
    return Path(_HARDCODED_DEFAULT)


def ensure_lingo_on_path() -> None:
    """Add Lingo_PERSONAS to sys.path if not already present."""
    lingo_str = str(get_lingo_root())
    if lingo_str not in sys.path:
        sys.path.insert(0, lingo_str)
