"""
Tests for lock_service.py
"""
import os
import threading
from pathlib import Path

import pytest

from src.lock_service import acquire_background_lock, release_background_lock


def test_acquire_and_release_lock(tmp_path):
    lock_path = tmp_path / "test.lock"
    assert acquire_background_lock(str(lock_path)) is True
    assert lock_path.exists()
    release_background_lock(str(lock_path))
    # On some systems the file might not be deleted immediately, but we don't strictly require that
    # Just check that we can acquire again
    assert acquire_background_lock(str(lock_path)) is True
    release_background_lock(str(lock_path))


def test_cannot_acquire_same_lock_twice(tmp_path):
    lock_path = tmp_path / "test.lock"
    assert acquire_background_lock(str(lock_path)) is True
    # Second acquire should fail
    assert acquire_background_lock(str(lock_path)) is False
    release_background_lock(str(lock_path))


def test_lock_released_in_thread():
    # Use a thread to test lock is released properly
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_path = Path(tmpdir) / "test.lock"
        result1 = [False]
        
        def thread1():
            result1[0] = acquire_background_lock(str(lock_path))
        
        t1 = threading.Thread(target=thread1)
        t1.start()
        t1.join()
        
        assert result1[0] is True
        
        # Now try to acquire from main thread
        result2 = acquire_background_lock(str(lock_path))
        assert result2 is False  # still locked by thread1's file descriptor
        
        release_background_lock(str(lock_path))
        
        # Now try again
        result3 = acquire_background_lock(str(lock_path))
        assert result3 is True
        release_background_lock(str(lock_path))
