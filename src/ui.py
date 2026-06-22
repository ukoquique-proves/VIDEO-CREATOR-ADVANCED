"""
Streamlit UI for interactive video generation.

Run with:
    python -m streamlit run src/ui.py
"""

import logging
import queue
import sys
import threading
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st

from src.schema import VideoConfiguration, VisualAssetConfig, VisualAssetType, Orientation, Language
from src.orchestrator import VideoOrchestrator


# ---------------------------------------------------------------------------
# Queue-based log handler
# ---------------------------------------------------------------------------

class _QueueHandler(logging.Handler):
    def __init__(self, log_queue: queue.Queue):
        super().__init__()
        self._queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        self._queue.put(self.format(record))


def _run_pipeline(config: VideoConfiguration, result_queue: queue.Queue, log_queue: queue.Queue) -> None:
    handler = _QueueHandler(log_queue)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    src_logger = logging.getLogger("src")  # project-local logs only
    src_logger.addHandler(handler)
    try:
        orchestrator = VideoOrchestrator(output_dir=str(project_root / "output"))
        result = orchestrator.create_video(config)
        result_queue.put(("ok", result))
    except Exception as exc:
        result_queue.put(("err", exc))
    finally:
        src_logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _init_state() -> None:
    defaults = {
        "running": False,
        "thread": None,
        "log_queue": None,
        "result_queue": None,
        "log_lines": [],
        "result": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _drain_logs() -> None:
    """Move any pending log messages from the queue into session_state.log_lines."""
    q = st.session_state.log_queue
    if q is None:
        return
    while True:
        try:
            st.session_state.log_lines.append(q.get_nowait())
        except queue.Empty:
            break


def _check_result() -> None:
    """If the pipeline finished, pull the result and mark as done."""
    q = st.session_state.result_queue
    if q is None:
        return
    try:
        st.session_state.result = q.get_nowait()
        st.session_state.running = False
    except queue.Empty:
        pass


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="VideoCreation UI", page_icon="🎥", layout="wide")
    st.title("🎥 VideoCreation UI")
    _init_state()

    # ---- Sidebar ----
    with st.sidebar:
        st.header("Settings")
        title = st.text_input("Video Title", value="My Generated Video")

        orientation_str = st.radio(
            "Orientation",
            options=[Orientation.VERTICAL.value, Orientation.HORIZONTAL.value],
            format_func=lambda x: x.capitalize(),
            help="Vertical (9:16) or Horizontal (16:9)",
        )

        subtitles_enabled = st.checkbox("Enable Subtitles", value=False)

        language_str = st.selectbox(
            "Language",
            options=[lang.value for lang in Language],
            format_func=lambda x: {
                "en": "English", "es": "Spanish", "zh": "Chinese",
                "fr": "French", "de": "German", "pt": "Portuguese",
            }.get(x, x.upper()),
        )

    # ---- Form ----
    st.header("Speech Content")
    speech_content = st.text_area(
        "Text to be spoken:",
        height=130,
        placeholder="Enter the speech content here.",
    )

    st.header("Visual Assets")
    asset_type_str = st.radio(
        "Visual Source",
        options=[
            VisualAssetType.TEXT_PROMPTS.value,
            VisualAssetType.IMAGE_SEQUENCE.value,
            VisualAssetType.MEDIA_SEQUENCE.value,
        ],
        format_func=lambda x: (
            "AI Generated (Text Prompts)"
            if x == "text_prompts"
            else ("User Provided (Local Images)" if x == "image_sequence" else "User Provided (Local Media — images or videos)")
        ),
    )

    prompts: list = []
    images: list = []
    uploaded_images: dict = {}

    if asset_type_str == VisualAssetType.TEXT_PROMPTS.value:
        raw = st.text_area("AI Prompts (one per line):", height=130,
                           placeholder="A futuristic city skyline at night\nA close-up of a neon sign")
        prompts = [p.strip() for p in raw.splitlines() if p.strip()]

        if any(p.startswith("/") or p.lower().endswith((".png", ".jpg", ".jpeg", ".webp")) for p in prompts):
            st.warning("⚠️ Some prompts look like file paths. If you want to use local images, switch the 'Visual Source' above to 'User Provided'.")
    else:
        # Accept video types too when the user selected the MEDIA_SEQUENCE option
        if asset_type_str == VisualAssetType.MEDIA_SEQUENCE.value:
            uploader_types = ["png", "jpg", "jpeg", "webp", "mp4", "mov", "webm", "mkv", "avi"]
            uploader_help = "Drag and drop image or video files here, or click to browse."
        else:
            uploader_types = ["png", "jpg", "jpeg", "webp"]
            uploader_help = "Drag and drop image files here, or click to browse."

        uploaded_files = st.file_uploader(
            "Drop or select files",
            type=uploader_types,
            accept_multiple_files=True,
            help=uploader_help,
        )

        raw = st.text_area(
            "OR enter local image paths (one per line):",
            height=80,
            placeholder="/path/to/image1.jpg\n/path/to/image2.png",
        )

        if uploaded_files:
            # Keep bytes in memory — the orchestrator saves them to disk at pipeline time.
            uploaded_images = {f.name: f.getvalue() for f in uploaded_files}
            st.info(f"{len(uploaded_files)} file(s) ready to use.")

        manual_paths = [p.strip() for p in raw.splitlines() if p.strip()]
        if manual_paths:
            images.extend(manual_paths)
            st.info(f"{len(manual_paths)} path(s) added.")

    st.divider()

    st.header("Audio Assets")
    uploaded_background_music: dict = {}
    background_music_path: str = st.text_input(
        "Background music path (local file)",
        value="",
        help="Optional local audio file path for background music.",
    )
    uploaded_audio_files = st.file_uploader(
        "Upload background music",
        type=["mp3", "wav", "aac", "m4a", "ogg"],
        accept_multiple_files=False,
        help="Upload one audio file to use as background music.",
    )
    if uploaded_audio_files:
        uploaded_background_music = {uploaded_audio_files.name: uploaded_audio_files.getvalue()}
        st.info(f"Background music file ready: {uploaded_audio_files.name}")

    st.divider()

    # ---- Generate button ----
    if st.button("🚀 Generate Video", use_container_width=True, disabled=st.session_state.running):
        errors = []
        if not title.strip():
            errors.append("Please provide a video title.")
        # UI-level guard: prevent path traversal or absolute paths from titles
        try:
            if ".." in title or "/" in title or "\\" in title or Path(title).is_absolute():
                errors.append("Invalid title: remove path separators or '..' sequences.")
        except Exception:
            errors.append("Invalid title: contains unsupported characters.")
        if not speech_content.strip():
            errors.append("Please provide speech content.")
        if asset_type_str == VisualAssetType.TEXT_PROMPTS.value and not prompts:
            errors.append("Please provide at least one AI prompt.")
        if asset_type_str in (VisualAssetType.IMAGE_SEQUENCE.value, VisualAssetType.MEDIA_SEQUENCE.value) and not images and not uploaded_images:
            errors.append("Please provide at least one image or media file (upload or path).")
        for err in errors:
            st.error(err)
        if errors:
            st.stop()

        config = VideoConfiguration(
            title=title,
            speech_content=speech_content,
            background_music=background_music_path.strip() or None,
            uploaded_background_music=uploaded_background_music or None,
            visual_assets=VisualAssetConfig(
                asset_type=VisualAssetType(asset_type_str),
                prompts=prompts or None,
                images=images or None,
                uploaded_images=uploaded_images or None,
            ),
            subtitles_enabled=subtitles_enabled,
            orientation=Orientation(orientation_str),
            language=Language(language_str),
        )

        st.session_state.log_lines = []
        st.session_state.result = None
        st.session_state.log_queue = queue.Queue()
        st.session_state.result_queue = queue.Queue()
        st.session_state.running = True

        st.session_state.thread = threading.Thread(
            target=_run_pipeline,
            args=(config, st.session_state.result_queue, st.session_state.log_queue),
            daemon=True,
        )
        st.session_state.thread.start()
        st.rerun()

    # ---- Live log output while running ----
    if st.session_state.running:
        _drain_logs()
        _check_result()

        st.info("Pipeline running…")
        if st.session_state.log_lines:
            st.code("\n".join(st.session_state.log_lines[-40:]))

        if st.session_state.running:
            # Still going — schedule another rerun after a short pause
            import time
            time.sleep(0.5)
            st.rerun()

    # ---- Show logs + result once done ----
    if not st.session_state.running and st.session_state.result is not None:
        _drain_logs()  # catch any final messages
        if st.session_state.log_lines:
            st.code("\n".join(st.session_state.log_lines))

        status, payload = st.session_state.result
        if status == "err":
            st.error(f"Pipeline failed: {payload}")
        else:
            result = payload
            st.success(f"Done — saved to: {result['output_path']}")
            if result["format"] in ("mp4", "webm"):
                with open(result["output_path"], "rb") as f:
                    st.video(f.read())
            else:
                st.info("Format not supported for in-browser playback — check the output directory.")


if __name__ == "__main__":
    main()
