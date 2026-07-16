"""
Chequeo mínimo de importación para ops-core --video-check.
Rápido, sin proveedores externos, sin generación real de video.
Activar test_smoke.py recién cuando TO_FIX.md #4, #5 y #7 estén cerrados.
"""

def test_core_modules_importable():
    from src.schema import VideoConfiguration  # noqa: F401
    from src.orchestrator import VideoOrchestrator  # noqa: F401

def test_cli_entry_point_exists():
    import importlib.util
    assert importlib.util.find_spec("src.main") is not None
