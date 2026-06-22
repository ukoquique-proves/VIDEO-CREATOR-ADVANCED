import os
import wave
from PIL import Image
from src import assembler_adapter


class DummyBackend:
    def assemble(self, **kwargs):
        # Simulate Lingo unavailable
        return None


def _write_silence_wav(path, duration=1.0, fps=44100):
    n_frames = int(duration * fps)
    with wave.open(path, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(fps)
        wav_file.writeframes(b'\x00\x00' * n_frames)


def test_local_fallback_with_background_music(tmp_path):
    audio = tmp_path / "speech.wav"
    _write_silence_wav(str(audio), duration=1.0)

    visuals_dir = tmp_path / "visuals"
    visuals_dir.mkdir()
    img = visuals_dir / "img.png"
    Image.new('RGB', (16, 16), color='blue').save(img)

    bg = tmp_path / "bg.wav"
    _write_silence_wav(str(bg), duration=2.0)

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    path = assembler_adapter.assemble_video(
        audio_path=str(audio),
        visual_files=[str(img)],
        title='mixtest',
        output_dir=str(out_dir),
        output_format='mp4',
        background_music=str(bg),
        width=480,
        height=640,
        duration=1.0,
        backend=DummyBackend(),
    )

    assert path is not None
    assert os.path.isfile(path)
    assert path.endswith('.mp4')
