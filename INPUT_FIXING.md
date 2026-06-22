# INPUT_FIXING

## Current architecture review

The project already relocates user-provided visual assets into the per-video workspace:
- `src/orchestrator.py` saves in-memory uploads to `workspace/visuals` via `_save_uploaded_images()`.
- `src/image_adapter.py` copies local provided visual files into `workspace/visuals/cached` via `copy_provided_images()`.
- `src/orchestrator.py` generates TTS from `speech_content` and writes it to `workspace/speech.mp3`.

This means images and video clips provided by the user are correctly moved into the video workspace.
- Speech text is converted to `workspace/speech.mp3` and is already handled inside the workspace.
- Background music is currently not copied into the workspace and requires the same treatment.

## Branch-derived design notes from `VideoCreation-03-arch3`

The broken branch contains several useful architectural patterns that can directly support our roadmap and input-fix work:

- `VideoGateway` is a clean adapter boundary: the orchestrator only knows a dataclass of plain callables, and configuration is resolved at wiring time.
- `ConfigLoader` is instanced per pipeline rather than relying on a single module-level cache; this is stronger for concurrent or batch execution.
- Uploaded image bytes are saved into `workspace/visuals` before copy/processing, which is exactly the workspace-local asset behavior we want.
- The local assembler already includes a working `background_music` mixing path when the file is present, so the missing piece is workspace-copying rather than mixing logic.
- Folder-watcher-style workspace cleanup and stale-workspace removal show a robust pattern for repeated batch runs.

These branch ideas reinforce the current fix plan: keep I/O boundary wiring at the gateway layer, isolate config per orchestrator instance, and ensure every user-provided asset is copied into the video workspace before assembly.

## Missing or incomplete input relocation

The architecture does not consistently relocate user-provided audio/background music:
- `VideoConfiguration.background_music` is accepted by the schema and passed through to the assembler.
- There is no explicit copy of `background_music` into the video workspace before assembly.
- The UI does not expose a file uploader or path entry for `background_music`, so user-provided audio is only supported via manual config changes.

Also, there is no support for direct user-provided narration audio files (only speech text via TTS).

This file now includes background music explicitly as a missing relocation path that must be fixed.

## Fix plan

### 1. Relocate all user media inputs into the workspace

- Add a workspace-safe audio directory, e.g. `workspace/audio`.
- Add a helper in `VideoOrchestrator` such as `_save_uploaded_audio()` to write uploaded audio bytes to disk.
- Add a helper such as `_copy_external_audio()` to copy a user-specified background music file into `workspace/audio`.
- Before assembly, rewrite `config.background_music` to point at the copied workspace audio path.
- If a user-specified audio path does not exist or is invalid, raise a clear error before assembly.

### 2. Extend schema and UI to support uploaded audio

- Extend `VisualAssetConfig` or `VideoConfiguration` with an `uploaded_audio: Optional[Dict[str, bytes]]` field, or a dedicated `uploaded_background_music` field.
- In `src/ui.py`, add a file uploader for background music when the user is creating video assets.
- Save uploaded audio bytes to the new audio workspace directory during pipeline execution.
- Add a UI warning if manual audio paths contain traversal segments or unsupported file types.

### 3. Harden path safety and normalization

- Ensure `sanitize_filename()` is used on uploaded audio file names before writing them to disk.
- For copied files, use only `os.path.basename(src)` when building the destination file name.
- Reject or sanitize any user-provided absolute or traversal-based video/audio paths at the UI or orchestrator boundary.

### 4. Add tests for input relocation

- Add a test confirming `background_music` local file paths are copied to `workspace/audio`.
- Add a test confirming uploaded audio bytes are saved to disk and used by the assembler.
- Add a test confirming manually provided local media files and upload bytes are both relocated for MEDIA_SEQUENCE.
- Add a regression test verifying `speech_content` always produces `workspace/speech.mp3`.

## Recommended implementation steps

1. Add `workspace/audio` creation and helper methods in `src/orchestrator.py`.
2. Copy `background_music` into the workspace and use the copied path for assembly.
3. Add UI support for uploaded background music / audio paths.
4. Add schema support for uploaded audio if necessary.
5. Add tests around background music copying, audio upload handling, and workspace relocation.

## Summary

- Images and videos are already relocated into the per-video workspace.
- Speech text is converted to speech audio inside the workspace.
- Background music/audio path handling is not yet implemented as a full relocation workflow.
- `INPUT_FIXING.md` documents the exact fix plan needed to make all user-provided assets consistently relocated.
