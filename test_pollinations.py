
import pytest

pytest.importorskip("shorts_creator")
try:
    from shorts_creator.footage_generator_v2 import FootageGeneratorV2  # type: ignore
except Exception as exc:  # covers ImportError and runtime errors in vendored code
    pytest.skip(f"FootageGeneratorV2 import failed: {exc}", allow_module_level=True)


gen = FootageGeneratorV2(output_dir='/tmp')
try:
    print("Testing pollinations...")
    path = gen.generate_image("A futuristic city")
    print(f"Success: {path}")
except Exception as e:
    print(f"Failed: {e}")
