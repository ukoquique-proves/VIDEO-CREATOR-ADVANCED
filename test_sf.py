
import pytest

pytest.importorskip("shorts_creator")
try:
	from shorts_creator.image_providers.siliconflow_provider import SiliconFlowProvider  # type: ignore
except Exception as exc:
	pytest.skip(f"SiliconFlowProvider import failed: {exc}", allow_module_level=True)


provider = SiliconFlowProvider(api_key="fake_key_123")
result = provider.generate("A cute cat", width=512, height=512, output_dir="test_out")
print("Success:", result.success)
print("Error:", result.error_message)
