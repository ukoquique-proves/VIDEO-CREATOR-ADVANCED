"""
Lock service for managing exclusive process locks.
"""

import fcntl
import os
import uuid
from pathlib import Path
from typing import Dict, Optional


# Global dictionary to hold open file descriptors for active locks
_LOCK_FDS: Dict[str, object] = {}


def acquire_background_lock(lock_path: Path | str) -> bool:
    """Prevent overlapping video generations by reserving a pid-file lock."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    global _LOCK_FDS
    try:
        _LOCK_FDS
    except NameError:
        _LOCK_FDS = {}

    f = open(path, "a+", encoding="utf-8")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        # Another process holds the lock
        try:
            # Attempt to read pid/uuid for diagnostics
            f.seek(0)
            info = f.read().strip()
        except Exception:
            info = ""
        f.close()
        return False

    # We have the lock — write PID + run UUID for diagnosability
    run_id = uuid.uuid4().hex
    f.seek(0)
    f.truncate(0)
    f.write(f"{os.getpid()} {run_id}\n")
    f.flush()
    # Keep file descriptor open to hold the lock
    _LOCK_FDS[str(path)] = f
    return True


def release_background_lock(lock_path: Path | str) -> None:
    """Release the pid-file guard for a finished generation."""
    global _LOCK_FDS
    try:
        _LOCK_FDS
    except NameError:
        _LOCK_FDS = {}

    key = str(Path(lock_path))
    f = _LOCK_FDS.pop(key, None)
    if f is not None:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            f.close()
        except Exception:
            pass
    try:
        Path(lock_path).unlink(missing_ok=True)
    except Exception:
        pass
