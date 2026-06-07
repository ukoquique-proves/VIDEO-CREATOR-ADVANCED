"""
Shared Lingo_PERSONAS utilities.

Centralises the LINGO_ROOT path resolution and sys.path injection so
adapters don't each duplicate this logic.

Path resolution order:
  1. LINGO_ROOT environment variable
  2. lingo.root in config/default_config.yaml
  3. Local ``vendor/Lingo_PERSONAS`` directory (last resort — may be outdated)
"""

import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_VENDOR_DEFAULT = _PROJECT_ROOT / "vendor" / "Lingo_PERSONAS"


def get_lingo_root() -> Path:
    """Resolve the Lingo_PERSONAS root directory.

    Checks, in order:
    1. ``LINGO_ROOT`` environment variable
    2. ``lingo.root`` in ``config/default_config.yaml``
    3. Local ``vendor/Lingo_PERSONAS`` directory (last resort — may be outdated)
    """
    # 1. Environment variable (highest priority — explicit operator override)
    env_val = os.environ.get("LINGO_ROOT")
    if env_val:
        p = Path(env_val)
        if p.exists() and p.is_dir():
            return p
        logger.warning("LINGO_ROOT env var points to non-existent path: %s", env_val)

    # 2. Config file
    try:
        from src import config_loader
        cfg_val = config_loader.lingo().get("root")
        if cfg_val:
            p = Path(cfg_val)
            if p.exists() and p.is_dir():
                return p
            logger.warning("lingo.root config points to non-existent path: %s", cfg_val)
    except Exception:
        pass  # config unavailable

    # 3. Local vendor directory (last resort)
    if _VENDOR_DEFAULT.exists() and _VENDOR_DEFAULT.is_dir():
        return _VENDOR_DEFAULT

    # Fallback to vendor path even if it doesn't exist yet (to maintain consistent return type)
    return _VENDOR_DEFAULT


def ensure_lingo_on_path() -> None:
    """Add Lingo_PERSONAS to sys.path if not already present."""
    lingo_str = str(get_lingo_root())
    if lingo_str not in sys.path:
        sys.path.insert(0, lingo_str)
