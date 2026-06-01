"""
Streamlit UI for interactive video generation.

Run with:
    python -m streamlit run src/ui.py
"""

import sys
import os
from pathlib import Path

# Add the project root to sys.path so we can import src modules
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
from src.schema import VideoConfiguration, VisualAssetConfig, VisualAssetType, Orientation, Language
from src.orchestrator import VideoOrchestrator

def main():
    st.set_page_config(page_title="VideoCreation UI", page_icon="🎥", layout="wide")
    
    st.title("🎥 VideoCreation UI")
    st.markdown("Generate videos interactively using the Lingo_PERSONAS pipeline.")
    
    with st.sidebar:
        st.header("1. Core Settings")
        title = st.text_input("Video Title", value="My Generated Video")
        
        orientation_str = st.radio(
            "Orientation",
            options=[Orientation.VERTICAL.value, Orientation.HORIZONTAL.value],
            format_func=lambda x: x.capitalize(),
            help="Vertical (9:16) or Horizontal (16:9)"
        )
        
        subtitles_enabled = st.checkbox("Enable Subtitles", value=True)
        
        language_options = [l.value for l in Language]
        language_str = st.selectbox(
            "Language",
            options=language_options,
            format_func=lambda x: dict(
                en="English", es="Spanish", zh="Chinese", fr="French", de="German", pt="Portuguese"
            ).get(x, x.upper())
        )
    
    st.header("2. Speech Content")
    speech_content = st.text_area(
        "Text to be spoken in the video:",
        height=150,
        placeholder="Enter the speech content here. Each sentence will be synthesized and timed."
    )
    
    st.header("3. Visual Assets")
    asset_type_str = st.radio(
        "Visual Source",
        options=[VisualAssetType.TEXT_PROMPTS.value, VisualAssetType.IMAGE_SEQUENCE.value],
        format_func=lambda x: "AI Generated (Text Prompts)" if x == "text_prompts" else "User Provided (Local Images)"
    )
    
    prompts = []
    images = []
    
    if asset_type_str == "text_prompts":
        raw_prompts = st.text_area(
            "AI Prompts (one per line):",
            height=150,
            placeholder="A futuristic city skyline at night...\nA close up of a neon sign..."
        )
        if raw_prompts.strip():
            prompts = [p.strip() for p in raw_prompts.split("\n") if p.strip()]
    else:
        raw_images = st.text_area(
            "Local Image Paths (one per line):",
            height=150,
            placeholder="/path/to/image1.jpg\n/path/to/image2.png"
        )
        if raw_images.strip():
            images = [i.strip() for i in raw_images.split("\n") if i.strip()]
            
    st.divider()
    
    if st.button("🚀 Generate Video", use_container_width=True):
        if not title.strip():
            st.error("Please provide a video title.")
            return
        if not speech_content.strip():
            st.error("Please provide speech content.")
            return
        if asset_type_str == "text_prompts" and not prompts:
            st.error("Please provide at least one AI prompt.")
            return
        if asset_type_str == "image_sequence" and not images:
            st.error("Please provide at least one local image path.")
            return
            
        with st.spinner("Generating video... This may take a few minutes depending on the backends."):
            try:
                config = VideoConfiguration(
                    title=title,
                    speech_content=speech_content,
                    visual_assets=VisualAssetConfig(
                        asset_type=VisualAssetType(asset_type_str),
                        prompts=prompts if prompts else None,
                        images=images if images else None,
                    ),
                    subtitles_enabled=subtitles_enabled,
                    orientation=Orientation(orientation_str),
                    language=Language(language_str)
                )
                
                orchestrator = VideoOrchestrator(output_dir="output")
                result = orchestrator.create_video(config)
                
                st.success(f"Video generated successfully! Saved to: {result['output_path']}")
                
                # Try to display the video if it's playable in browser (mp4/webm)
                if result['format'] in ['mp4', 'webm']:
                    with open(result['output_path'], 'rb') as f:
                        st.video(f.read())
                else:
                    st.info("Video format is not supported for in-browser playback. Check the output directory.")
                    
            except Exception as e:
                st.error(f"An error occurred during video generation:\n\n{str(e)}")


if __name__ == "__main__":
    main()
