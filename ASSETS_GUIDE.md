# Asset Organization Guide

This guide explains how to organize your input assets (images, short videos, audio files, and speech text) when using VideoCreation.

## Directory Structure (Recommended)

```
VideoCreation/
├── config/               # Video configuration YAML/JSON files
│   └── your_video.yaml   # Your video recipe
├── assets/               # Your source materials go here
│   ├── your_video/       # Per-video assets (recommended)
│   │   ├── audio/        # Background music files
│   │   ├── visuals/      # Images and video clips
│   └── shared/           # Reusable assets across videos
│       ├── audio/
│       └── visuals/
├── output/               # Generated videos (auto-created)
└── output/logs/          # Background generation logs (auto-created)
```

## How to Reference Assets in Your Config

### 1. Speech
You have two options for speech:

#### Option 1: Text-to-Speech
Use `speech_content` directly in your config:
```yaml
title: "My Video"
speech_content: "This is the audio narration for my video. It will be converted to speech automatically."
```

#### Option 2: Pre-made Audio
Use `speech_audio` to skip TTS and use your own file:
```yaml
title: "My Video"
speech_audio: "assets/your_video/audio/narration.mp3"
```

### 2. Visuals (Images or Video Clips)
Use `visual_assets` with `asset_type: media_sequence` and point to files in your `assets/` directory:

```yaml
visual_assets:
  asset_type: media_sequence
  images:
    - "assets/your_video/visuals/image1.png"
    - "assets/your_video/visuals/clip1.mp4"
```

Alternatively, use AI prompts (no files needed):
```yaml
visual_assets:
  asset_type: text_prompts
  prompts:
    - "A peaceful mountain landscape"
    - "A person smiling at the camera"
```

### 3. Background Music
Point to an audio file in `assets/`:
```yaml
background_music: "assets/shared/audio/soft_piano.mp3"
```

## How to Run

### Foreground (default)
```bash
python -m src.main --config config/escenas.yaml
```

### Background (detached process)
```bash
python -m src.main --config config/escenas.yaml --background
```
The background process will log to `output/logs/Your Video.log`.

## Workspace Directory (Auto-Created)
Do **NOT** use the `workspace/` directory to store source materials! This is an internal, temporary directory the pipeline uses to organize files during generation. It will be cleaned up automatically (or replaced on each run).

## Tips
- **Keep assets organized** per video or by type
- **Use relative paths** from the project root in your config files
- **Never hardcode absolute paths** if you want your config to work on different machines
- Use `--background` for long-running video generations so you don't have to wait!
