from pathlib import Path

from src.main import _acquire_background_lock, _release_background_lock


def test_background_lock_prevents_duplicate_generation(tmp_path: Path) -> None:
    lock_path = tmp_path / "video.lock"

    assert _acquire_background_lock(lock_path) is True
    assert _acquire_background_lock(lock_path) is False

    _release_background_lock(lock_path)
    assert not lock_path.exists()
