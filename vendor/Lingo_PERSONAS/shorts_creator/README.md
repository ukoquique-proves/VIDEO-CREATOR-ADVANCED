# AI Shorts Creator Module

Automated short-form video creation for TikTok, Instagram Reels, and YouTube Shorts.

## Features

- **AI Script Writing**: Generate engaging scripts with hooks, CTAs, and proper pacing
- **TTS Voiceover**: Multiple voice options (Edge TTS - free, Azure, OpenAI)
- **Visual Generation**: 
  - Stock footage from Pexels/Pixabay
  - AI-generated images via free APIs (Pollinations, FLUX, Stable Diffusion)
- **Video Assembly**: Automatic assembly with captions, transitions, and music

## Quick Start

### Option 1: Via VideoLingo Main App

```bash
# Start VideoLingo
.venv/bin/streamlit run st.py
```

Then click the "🎬 AI Shorts Creator" tab.

### Option 2: Standalone Mode

```bash
# Start Shorts Creator directly
.venv/bin/streamlit run launch_shorts.py
```

## Usage

### Quick Create

1. Enter your video topic
2. Select duration (15-90 seconds)
3. Choose content style
4. Click "Create Video"

### Advanced Options

- **Script Settings**: Customize tone, hook type, target audience
- **Voice Settings**: Choose TTS engine and voice
- **Visual Settings**: Prefer stock footage or AI-generated, image style
- **Video Settings**: Captions, background music

## API Keys (Optional)

For enhanced features, you can add API keys:

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| Pexels | Stock footage/images | Yes |
| Pixabay | Stock footage/images | Yes |
| HuggingFace | FLUX/SD image generation | Yes |

Without API keys, the module uses:
- **Pollinations.ai** for free AI image generation
- **Edge TTS** for free voice synthesis

## Programmatic Usage

```python
from shorts_creator.shorts_workflow import ShortsWorkflow, WorkflowConfig

# Configure
config = WorkflowConfig(
    script_duration=60,
    script_style='educational',
    tts_method='edge_tts',
    image_engine='pollinations'
)

# Create workflow
workflow = ShortsWorkflow(config)

# Create video
result = workflow.create_video("5 productivity tips that actually work")
print(f"Video saved to: {result['video_path']}")
```

### Quick Function

```python
from shorts_creator.shorts_workflow import quick_create_video

video_path = quick_create_video(
    topic="The science of habits",
    duration=60,
    style='educational'
)
```

## Module Structure

```
shorts_creator/
├── __init__.py           # Module exports
├── script_generator.py   # AI script generation
├── footage_generator.py  # Stock/AI visual generation
├── video_assembler.py    # Video compilation
├── shorts_workflow.py    # Complete workflow orchestration
├── shorts_ui.py          # Streamlit interface
└── README.md             # This file
```

## Output Structure

```
output/shorts/
├── scripts/     # Generated scripts (JSON)
├── audio/       # Voiceover segments (WAV)
├── footage/     # Visual assets
│   ├── stock/   # Downloaded stock media
│   └── generated/ # AI-generated images
└── final/       # Completed videos (MP4)
```

## Content Styles

| Style | Description |
|-------|-------------|
| educational | Teaching content, informative |
| entertainment | Fun, engaging content |
| motivational | Inspiring, uplifting |
| how_to | Tutorial, step-by-step |
| listicle | List-based (e.g., "5 tips...") |
| facts | Interesting facts/trivia |
| storytelling | Narrative content |
| news | Trending topics |

## Tips for Best Results

1. **Specific Topics**: More specific topics yield better scripts
2. **Short Durations**: 30-60 seconds work best for engagement
3. **Clear Hooks**: The first 2 seconds are crucial
4. **Visual Relevance**: Match visuals to script content
5. **Consistent Style**: Use same voice/style for series

## Troubleshooting

### No visuals generated
- Check internet connection
- Try different image engine
- Add HuggingFace API key for FLUX/SD

### TTS not working
- Edge TTS requires internet
- Azure/OpenAI require API keys
- Check config.yaml for TTS settings

### Video assembly fails
- Ensure ffmpeg is installed
- Check audio files exist
- Verify visual files are valid images/videos

## License

Part of VideoLingo - Apache 2.0 License

## Documentation

- `../AI_VIDEO_SHORTS.md` - Complete feature documentation
- `../QUICKSTART.md` - Quick start guide
- `../CHANGELOG.md` - Technical changes only
