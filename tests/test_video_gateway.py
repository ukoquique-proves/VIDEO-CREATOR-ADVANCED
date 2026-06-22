import os
from src.video_gateway import VideoGateway
from src.orchestrator import VideoOrchestrator
from src.schema import VideoConfiguration, VisualAssetConfig, VisualAssetType


def test_orchestrator_accepts_gateway_and_uses_it(tmp_path):
    # Prepare a minimal configuration
    cfg = VideoConfiguration(
        title="gw-test",
        speech_content="hello",
        visual_assets=VisualAssetConfig(asset_type=VisualAssetType.TEXT_PROMPTS, prompts=["a test"]),
    )

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # Create dummy callables
    def dummy_tts(text, output_path, language=None, method=None, rate=None):
        with open(output_path, "wb") as f:
            f.write(b"audio")

    def dummy_generate(prompts, visuals_dir, **kwargs):
        # create a single dummy image file
        p = os.path.join(visuals_dir, "img1.png")
        with open(p, "wb") as f:
            f.write(b"png")
        return [p]

    def dummy_copy(images, visuals_dir):
        # just return the list as-is (assume they exist)
        return list(images)

    def dummy_modify(files, instr):
        return files

    def dummy_assemble(**kwargs):
        out = os.path.join(kwargs["output_dir"], "final.mp4")
        with open(out, "wb") as f:
            f.write(b"mp4")
        return out

    gateway = VideoGateway(
        tts=dummy_tts,
        generate_from_prompts=dummy_generate,
        copy_provided_images=dummy_copy,
        modify_images=dummy_modify,
        assemble_video=dummy_assemble,
    )

    orch = VideoOrchestrator(output_dir=str(out_dir), gateway=gateway)

    result = orch.create_video(cfg)
    assert result["output_path"]
    assert os.path.exists(result["output_path"]) is True
