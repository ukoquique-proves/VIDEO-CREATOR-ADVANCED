Act as an expert backend developer and software architect. I need you to scaffold a video generation application based on clear user instructions.

This project will build upon existing development found in:
`/root/a_VIDEO_GENERATION/VIDEO_PERSONAS/Lingo_PERSONAS` (utilize and integrate with this existing codebase where applicable).

The application must accept the following user configuration:
- Video Title
- Video Length (in minutes or seconds)
- Speech Content (plain text to be converted to audio)
- Background Music/Audio (optional)
- Visual Assets: A sequence of images to be shown consecutively (like slides) OR text prompts to generate these images using AI.
- Image Modification: Optional instructions to modify provided/generated images using AI.
- Subtitles: Optional toggle to burn subtitles onto the video.
- Output Format: Default to .mp4, with options for other standard formats.

Requirements:
1. **Test Suite:** Create a robust test suite inside a `tests/` folder. It must include multiple test cases demonstrating different creation flows (e.g., a minimal video, a video with AI image generation, a video with subtitles, etc.) using short/fast-rendering placeholders.
2. **Documentation:** - Create a comprehensive `README.md` explaining the project architecture, setup, and how to run the test suite.
   - Create a `ROADMAP.md` detailing the development phases, using markdown checkboxes (- [ ] ) to track progress.

Please generate the file structures, the core integration logic, the README.md, and the ROADMAP.md.
