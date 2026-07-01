from pathlib import Path

from unittest.mock import patch

from src.orchestrator import VideoOrchestrator
from src.schema import VideoConfiguration, VisualAssetConfig, VisualAssetType, Language, Orientation


def test_tts_voice_propagates_to_tts_adapter(tmp_path: Path) -> None:
    orch = VideoOrchestrator(output_dir=str(tmp_path / "output"))
    image_path = tmp_path / "img1.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    cfg = VideoConfiguration(
        title="Voice Test",
        speech_content="This should use the sweet voice.",
        visual_assets=VisualAssetConfig(
            asset_type=VisualAssetType.IMAGE_SEQUENCE,
            images=[str(image_path)],
        ),
        language=Language.SPANISH,
        orientation=Orientation.VERTICAL,
        tts_voice="es-MX-DaliaNeural",
    )

    with patch("src.orchestrator.tts_adapter.generate_speech") as mock_tts, \
         patch("src.assembler_adapter.assemble_video") as mock_assemble:
        speech_path = Path(tmp_path / "output" / "Voice_Test" / "speech.mp3")
        speech_path.parent.mkdir(parents=True, exist_ok=True)
        speech_path.write_bytes(b"mock audio data")
        mock_tts.return_value = str(speech_path)
        mock_output = str(tmp_path / "output" / "Voice_Test.mp4")
        mock_assemble.return_value = mock_output
        # Create mock output file so orchestrator thinks it exists
        Path(mock_output).parent.mkdir(parents=True, exist_ok=True)
        open(mock_output, "w").close()
        orch.create_video(cfg)

    assert mock_tts.call_count == 1
    assert mock_tts.call_args.kwargs["voice"] == "es-MX-DaliaNeural"
