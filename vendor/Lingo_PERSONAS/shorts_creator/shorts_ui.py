"""
Streamlit UI for Shorts Creator

Provides a user-friendly interface for creating short-form videos.
"""

import streamlit as st
import os
import sys
import json
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import load_key
from .shorts_workflow import ShortsWorkflow, WorkflowConfig


def shorts_creator_page():
    """Main page for Shorts Creator feature."""
    st.header("🎬 AI Shorts Creator")
    
    st.markdown("""
    <p style='font-size: 18px; color: #888;'>
    Create TikTok/Reels/YouTube Shorts style videos automatically using AI.
    Generate scripts, voiceovers, and visuals - all in one click!
    </p>
    """, unsafe_allow_html=True)
    
    # Create tabs for different modes
    tab1, tab2, tab3 = st.tabs(["Quick Create", "Advanced", "History"])
    
    with tab1:
        quick_create_section()
    
    with tab2:
        advanced_create_section()
    
    with tab3:
        history_section()


def quick_create_section():
    """Simple video creation interface."""
    st.subheader("Quick Video Creation")
    
    # Topic input
    topic = st.text_input(
        "Video Topic",
        placeholder="e.g., 5 tips for better productivity",
        help="Enter the main topic or subject for your video"
    )
    
    # Quick settings
    col1, col2 = st.columns(2)
    
    with col1:
        duration = st.select_slider(
            "Duration (seconds)",
            options=[15, 30, 45, 60, 90],
            value=60,
            help="Target video length"
        )
        
        style = st.selectbox(
            "Content Style",
            options=[
                'educational',
                'entertainment', 
                'motivational',
                'how_to',
                'listicle',
                'facts',
                'storytelling'
            ],
            format_func=lambda x: x.replace('_', ' ').title()
        )
    
    with col2:
        language = st.selectbox(
            "Script Language",
            options=['English', 'Spanish', 'French', 'German', 'Chinese', 'Japanese', 'Portuguese'],
            index=0
        )
        
        tone = st.selectbox(
            "Tone",
            options=['casual', 'professional', 'enthusiastic', 'calm'],
            format_func=lambda x: x.title()
        )
        
        voice = st.selectbox(
            "Voice",
            options=['en-US-GuyNeural', 'en-US-JennyNeural', 'en-GB-RyanNeural', 'en-GB-SoniaNeural'],
            format_func=lambda x: x.replace('-', ' ').replace('Neural', '').strip()
        )
        
        aspect_ratio = st.selectbox(
            "Aspect Ratio",
            options=['9:16', '16:9'],
            format_func=lambda x: "Mobile (9:16)" if x == '9:16' else "Desktop (16:9)"
        )

    
    # Create button
    if st.button("🎬 Create Video", type="primary", use_container_width=True):
        if not topic:
            st.error("Please enter a video topic!")
        else:
            create_video_workflow(
                topic=topic,
                duration=duration,
                style=style,
                language=language,
                tone=tone,
                voice=voice,
                aspect_ratio=aspect_ratio

            )


def advanced_create_section():
    """Advanced video creation with full customization."""
    st.subheader("Advanced Video Creation")
    
    # Script settings
    with st.expander("📝 Script Settings", expanded=True):
        topic = st.text_area(
            "Video Topic / Description",
            placeholder="Describe your video topic in detail...",
            height=100
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            style = st.selectbox(
                "Content Style",
                options=[
                    'educational', 'entertainment', 'motivational',
                    'how_to', 'listicle', 'facts', 'storytelling', 'news'
                ],
                format_func=lambda x: x.replace('_', ' ').title()
            )
            
            duration = st.number_input(
                "Duration (seconds)",
                min_value=15,
                max_value=180,
                value=60
            )
        
        with col2:
            tone = st.selectbox(
                "Tone",
                options=['casual', 'professional', 'humorous', 'dramatic', 'inspirational'],
                format_func=lambda x: x.title()
            )
            
            language = st.selectbox(
                "Language",
                options=['English', 'Spanish', 'French', 'German', 'Chinese', 'Japanese'],
                index=0
            )
        
        with col3:
            hook_type = st.selectbox(
                "Opening Hook Type",
                options=['question', 'statement', 'story', 'fact', 'challenge'],
                format_func=lambda x: x.title()
            )
            
            target_audience = st.text_input(
                "Target Audience",
                placeholder="e.g., young professionals",
                value="general"
            )
    
    # Voice settings
    with st.expander("🎙️ Voice Settings"):
        tts_method = st.selectbox(
            "TTS Method",
            options=['edge_tts', 'azure_tts', 'openai_tts'],
            format_func=lambda x: {
                'edge_tts': 'Edge TTS (Free)',
                'azure_tts': 'Azure TTS',
                'openai_tts': 'OpenAI TTS'
            }.get(x, x)
        )
        
        if tts_method == 'edge_tts':
            voice = st.selectbox(
                "Voice",
                options=[
                    'en-US-GuyNeural', 'en-US-JennyNeural',
                    'en-GB-RyanNeural', 'en-GB-SoniaNeural',
                    'en-AU-WilliamNeural', 'en-AU-NatashaNeural'
                ]
            )
        elif tts_method == 'azure_tts':
            voice = st.selectbox(
                "Voice",
                options=[
                    'en-US-GuyNeural', 'en-US-JennyNeural',
                    'en-US-BrandonNeural', 'en-US-AriaNeural'
                ]
            )
        else:
            voice = st.selectbox(
                "Voice",
                options=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
            )
    
    # Visual settings
    with st.expander("🖼️ Visual Settings"):
        prefer_stock = st.checkbox("Prefer stock footage over AI-generated", value=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            image_style = st.selectbox(
                "Image Style",
                options=['photorealistic', 'cinematic', 'artistic', 'cartoon', 'minimal', 'dramatic'],
                format_func=lambda x: x.title()
            )
        
        with col2:
                }.get(x, x)
            )
            
            aspect_ratio = st.selectbox(
                "Aspect Ratio",
                options=['9:16', '16:9', '1:1'],
                format_func=lambda x: {
                    '9:16': 'Mobile (9:16)',
                    '16:9': 'Desktop (16:9)',
                    '1:1': 'Square (1:1)'
                }.get(x, x)
            )

        
        # API keys for stock footage
        st.markdown("**API Keys (Optional)**")
        pexels_key = st.text_input("Pexels API Key", type="password")
        pixabay_key = st.text_input("Pixabay API Key", type="password")
        huggingface_key = st.text_input("HuggingFace API Key", type="password")
    
    # Video settings
    with st.expander("🎥 Video Settings"):
        add_captions = st.checkbox("Add captions", value=True)
        add_music = st.checkbox("Add background music", value=False)
        
        if add_music:
            music_file = st.file_uploader("Upload background music", type=['mp3', 'wav'])
    
    # Create button
    if st.button("🎬 Create Video", type="primary", use_container_width=True):
        if not topic:
            st.error("Please enter a video topic!")
        else:
            config = WorkflowConfig(
                script_style=style,
                script_duration=duration,
                script_tone=tone,
                script_language=language,
                tts_method=tts_method,
                tts_voice=voice,
                prefer_stock=prefer_stock,
                image_style=image_style,
                image_engine=image_engine,
                aspect_ratio=aspect_ratio,
                add_captions=add_captions,
                add_background_music=add_music

            )
            
            workflow = ShortsWorkflow(
                config=config,
                pexels_key=pexels_key if pexels_key else None,
                pixabay_key=pixabay_key if pixabay_key else None,
                huggingface_key=huggingface_key if huggingface_key else None
            )
            
            create_video_with_workflow(workflow, topic)


def history_section():
    """Show previously created videos."""
    st.subheader("Created Videos History")
    
    output_dir = Path('output/shorts/final')
    
    if not output_dir.exists():
        st.info("No videos created yet. Create your first video!")
        return
    
    videos = list(output_dir.glob("*.mp4"))
    
    if not videos:
        st.info("No videos found. Create your first video!")
        return
    
    for video_path in sorted(videos, reverse=True)[:10]:
        with st.container():
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**{video_path.stem}**")
                st.caption(f"Created: {time.ctime(video_path.stat().st_mtime)}")
            
            with col2:
                if st.button("▶️ Play", key=f"play_{video_path.name}"):
                    st.video(str(video_path))
                
                with open(video_path, 'rb') as f:
                    st.download_button(
                        "📥 Download",
                        f,
                        file_name=video_path.name,
                        key=f"dl_{video_path.name}"
                    )


def create_video_workflow(topic: str, duration: int, style: str, 
                          language: str, tone: str, voice: str, aspect_ratio: str = '9:16'):

    """Create video with progress display."""
    config = WorkflowConfig(
        script_duration=duration,
        script_style=style,
        script_language=language,
        script_tone=tone,
        tts_voice=voice,
        aspect_ratio=aspect_ratio
    )

    
    workflow = ShortsWorkflow(config)
    create_video_with_workflow(workflow, topic)


def create_video_with_workflow(workflow: ShortsWorkflow, topic: str):
    """Execute the video creation workflow with progress updates."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    def update_progress(percent, message):
        progress_bar.progress(percent)
        status_text.info(message)
    
    try:
        with st.spinner("Creating your video..."):
            result = workflow.create_video(
                topic=topic,
                progress_callback=update_progress
            )
        
        progress_bar.progress(100)
        status_text.success("✅ Video created successfully!")
        
        # Show results
        st.balloons()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📄 Generated Script")
            script = result.get('script', {})
            
            st.write(f"**Title:** {script.get('title', 'N/A')}")
            st.write(f"**Hook:** {script.get('hook', 'N/A')}")
            
            with st.expander("View Full Script"):
                st.write(script.get('full_script', 'No script generated'))
            
            with st.expander("View Segments"):
                for i, seg in enumerate(script.get('segments', [])):
                    st.write(f"**Segment {i+1}:** {seg.get('text', '')}")
                    st.caption(f"Visual: {seg.get('visual_suggestion', 'N/A')}")
        
        with col2:
            st.subheader("🎬 Final Video")
            
            if result.get('video_path'):
                st.video(result['video_path'])
                
                with open(result['video_path'], 'rb') as f:
                    st.download_button(
                        "📥 Download Video",
                        f,
                        file_name=os.path.basename(result['video_path']),
                        type="primary"
                    )
        
        # Show hashtags
        if script.get('hashtags'):
            st.subheader("# Hashtags")
            st.write(" ".join(script['hashtags']))
        
    except Exception as e:
        progress_bar.empty()
        status_text.error(f"❌ Error: {str(e)}")
        st.exception(e)


# For integration with main VideoLingo app
def get_shorts_tab():
    """Return the shorts creator tab content for integration."""
    return shorts_creator_page


if __name__ == '__main__':
    # Standalone mode
    st.set_page_config(page_title="AI Shorts Creator", page_icon="🎬")
    shorts_creator_page()
