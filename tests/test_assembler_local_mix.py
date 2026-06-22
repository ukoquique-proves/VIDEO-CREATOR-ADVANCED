
import os
from src import assembler_adapter


def test_local_assembler_with_background_music(tmp_path, monkeypatch):
    called = {}

    def fake_local(*args, **kwargs):
        # record that we were called and return a fake path
        called['args'] = args
        called['kwargs'] = kwargs
        out = os.path.join(kwargs['output_dir'], kwargs['output_filename'])
        with open(out, 'wb') as f:
            f.write(b'mp4')
        return out

    # Patch the local assembler to avoid running moviepy in tests
    monkeypatch.setattr(assembler_adapter, '_local_moviepy_assemble', fake_local)

    audio = tmp_path / "speech.mp3"
    audio.write_bytes(b'audio')
    visuals_dir = tmp_path / "visuals"
    visuals_dir.mkdir()
    img = visuals_dir / "img.png"
    img.write_bytes(b'png')
    bg = tmp_path / "bg.mp3"
    bg.write_bytes(b'bg')

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
    )

    assert path is not None
    assert os.path.exists(path)
    assert 'kwargs' in called
    assert called['kwargs']['background_music'] == str(bg)

