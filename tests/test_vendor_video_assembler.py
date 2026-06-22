import os
from pathlib import Path


def test_video_assembler_loops_and_strips_audio(tmp_path, sample_audio):
    """Ensure the vendored VideoAssembler can process short video clips
    that need looping without raising audio-reader exceptions.
    """
    # Import vendored assembler directly from file to avoid importing
    # package-level dependencies (e.g. openai) from shorts_creator.__init__
    import importlib.util
    project_root = Path(__file__).resolve().parent.parent
    va_path = project_root / "vendor" / "Lingo_PERSONAS" / "shorts_creator" / "video_assembler.py"
    spec = importlib.util.spec_from_file_location("shorts_creator.video_assembler", str(va_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    VideoAssembler = mod.VideoAssembler

    project_root = Path(__file__).resolve().parent.parent
    test_videos = project_root / "tests" / "test_VIDEOS"
    v1 = test_videos / "smallVideo1.mp4"
    v2 = test_videos / "smallVideo2.mp4"

    assert v1.exists() and v2.exists(), f"Test videos not found in {test_videos}"

    out_dir = str(tmp_path / "out")
    assembler = VideoAssembler(output_dir=out_dir)

    # create_simple_video uses AudioFileClip + _create_clip_from_file; if
    # _create_clip_from_file doesn't strip audio, moviepy may raise during
    # concatenation/compose. The test ensures the call completes and writes
    # a non-empty output file.
    out_path = assembler.create_simple_video("script", sample_audio, [str(v1), str(v2)])

    assert os.path.exists(out_path)
    assert os.path.getsize(out_path) > 0
