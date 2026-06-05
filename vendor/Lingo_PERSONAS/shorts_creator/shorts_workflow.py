"""
Shorts Workflow - Complete automated short-form video creation

Orchestrates the entire process:
1. Generate script using AI
2. Generate voiceover using TTS
3. Fetch/generate visuals
4. Assemble final video

Usage:
    from shorts_creator.shorts_workflow import ShortsWorkflow
    
    workflow = ShortsWorkflow()
    video_path = workflow.create_video("The science of productivity")
"""

import os
import sys
import json
import time
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import load_key
from core.tts_backend.tts_main import tts_main
from pydub import AudioSegment

from .script_generator import ScriptGenerator
from .footage_generator_v2 import FootageGeneratorV2 as FootageGenerator
from .video_assembler import VideoAssembler, VideoConfig
from .cleanup import auto_cleanup_before_creation, print_cleanup_report


@dataclass
class WorkflowConfig:
    """Configuration for the shorts workflow."""
    # Script settings
    script_style: str = 'educational'
    script_duration: int = 60
    script_tone: str = 'casual'
    script_language: str = 'English'
    
    # TTS settings
    tts_method: str = 'edge_tts'  # Free option
    tts_voice: str = 'en-US-GuyNeural'
    
    # Visual settings
    prefer_stock: bool = True
    image_style: str = 'photorealistic'
    image_engine: str = 'pollinations'  # Free option
    aspect_ratio: str = '9:16'         # '9:16' for mobile, '16:9' for desktop

    
    # Video settings
    add_captions: bool = True
    add_background_music: bool = False
    background_music_path: str = ''
    
    # Output settings
    output_dir: str = 'output/shorts'


class ShortsWorkflow:
    """Complete workflow for automated short-form video creation."""
    
    def __init__(self, config: WorkflowConfig = None, 
                 pexels_key: str = None, pixabay_key: str = None,
                 huggingface_key: str = None):
        """Initialize the workflow.
        
        Args:
            config: Workflow configuration
            pexels_key: Pexels API key for stock footage
            pixabay_key: Pixabay API key for stock footage
            huggingface_key: HuggingFace API key for AI image generation
        """
        self.config = config or WorkflowConfig()
        
        # Initialize components
        self.script_generator = ScriptGenerator()
        self.footage_generator = FootageGenerator(
            output_dir=os.path.join(self.config.output_dir, 'footage'),
            pexels_key=pexels_key,
            pixabay_key=pixabay_key,
            huggingface_key=huggingface_key
        )
        # Configure video dimensions based on aspect ratio
        size_map = {
            '9:16': (1080, 1920),
            '16:9': (1920, 1080),
            '1:1': (1080, 1080),
        }
        width, height = size_map.get(self.config.aspect_ratio, (1080, 1920))
        
        self.video_assembler = VideoAssembler(
            output_dir=self.config.output_dir,
            config=VideoConfig(width=width, height=height)
        )

        
        # Create output directories
        self._setup_directories()
    
    def _setup_directories(self):
        """Create necessary output directories."""
        dirs = [
            self.config.output_dir,
            os.path.join(self.config.output_dir, 'scripts'),
            os.path.join(self.config.output_dir, 'audio'),
            os.path.join(self.config.output_dir, 'footage'),
            os.path.join(self.config.output_dir, 'final'),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
    
    def create_video(self, topic: str, 
                     custom_config: Dict = None,
                     progress_callback=None) -> Dict:
        """Create a complete short-form video from a topic.
        
        Args:
            topic: The video topic/subject
            custom_config: Override default configuration
            progress_callback: Function to call with progress updates
            
        Returns:
            Dict with video path and metadata
        """
        config = self.config
        if custom_config:
            # Update config with custom values
            for key, value in custom_config.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        result = {
            'topic': topic,
            'status': 'started',
            'steps_completed': [],
            'files': {}
        }
        
        try:
            # Step 0: Cleanup old temporary files
            if progress_callback:
                progress_callback(5, 'Cleaning up old files...')
            
            cleanup_stats = auto_cleanup_before_creation(output_dir=self.config.output_dir)
            if cleanup_stats['deleted_files'] and progress_callback:
                # Silently cleanup, only report if there were files deleted
                pass
            
            # Step 1: Generate Script
            if progress_callback:
                progress_callback(10, 'Generating script...')
            
            script_data = self._generate_script(topic)
            result['script'] = script_data
            result['steps_completed'].append('script_generation')
            result['files']['script'] = self._save_script(script_data, topic)
            
            # Step 2: Generate Voiceover
            if progress_callback:
                progress_callback(30, 'Generating voiceover...')
            
            audio_files = self._generate_voiceover(script_data)
            result['steps_completed'].append('voiceover_generation')
            result['files']['audio'] = audio_files
            
            # Step 3: Generate/Fetch Visuals
            if progress_callback:
                progress_callback(50, 'Preparing visuals...')
            
            visual_files = self._prepare_visuals(script_data)
            result['steps_completed'].append('visual_preparation')
            result['files']['visuals'] = visual_files
            
            # Step 4: Assemble Video
            if progress_callback:
                progress_callback(70, 'Assembling video...')
            
            video_path = self._assemble_video(script_data, audio_files, visual_files)
            result['steps_completed'].append('video_assembly')
            result['video_path'] = video_path
            result['files']['video'] = video_path
            
            # Step 5: Finalize
            if progress_callback:
                progress_callback(90, 'Finalizing...')
            
            result['status'] = 'completed'
            result['completed_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
            
            if progress_callback:
                progress_callback(100, 'Complete!')
            
        except Exception as e:
            result['status'] = 'failed'
            result['error'] = str(e)
            raise
        
        return result
    
    def create_video_series(self, main_topic: str, num_videos: int = 5,
                            progress_callback=None) -> List[Dict]:
        """Create a series of related videos.
        
        Args:
            main_topic: The overarching topic
            num_videos: Number of videos to create
            progress_callback: Progress update function
            
        Returns:
            List of result dicts for each video
        """
        results = []
        
        # Generate series scripts
        scripts = self.script_generator.generate_script_series(
            main_topic, 
            num_videos,
            self.config.script_style,
            self.config.script_duration
        )
        
        for i, script_data in enumerate(scripts):
            if progress_callback:
                progress = int((i / num_videos) * 100)
                progress_callback(progress, f'Creating video {i+1}/{num_videos}...')
            
            try:
                result = self.create_video(
                    script_data['topic'],
                    custom_config={'script_duration': self.config.script_duration}
                )
                result['part_number'] = i + 1
                results.append(result)
            except Exception as e:
                results.append({
                    'status': 'failed',
                    'error': str(e),
                    'part_number': i + 1
                })
        
        return results
    
    def _generate_script(self, topic: str) -> Dict:
        """Generate script for the video."""
        return self.script_generator.generate_script(
            topic=topic,
            style=self.config.script_style,
            duration=self.config.script_duration,
            tone=self.config.script_tone,
            language=self.config.script_language
        )
    
    def _save_script(self, script_data: Dict, topic: str) -> str:
        """Save script to file."""
        safe_topic = "".join(c for c in topic[:30] if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"script_{safe_topic}_{int(time.time())}.json"
        filepath = os.path.join(self.config.output_dir, 'scripts', filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(script_data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def _generate_voiceover(self, script_data: Dict) -> List[str]:
        """Generate voiceover audio for each segment."""
        audio_dir = os.path.join(self.config.output_dir, 'audio')
        audio_files = []
        
        segments = script_data.get('segments', [])
        
        # If no segments, use full script
        if not segments:
            segments = [{'text': script_data.get('full_script', ''), 'duration_estimate': 60}]
        
        # Set TTS method in config
        from core.utils import update_key
        update_key("tts_method", self.config.tts_method)
        
        # Validate TTS method (only df-independent backends supported)
        SAFE_TTS_METHODS = ('edge_tts', 'azure_tts', 'openai_tts', 'fish_tts', 'custom_tts')
        if self.config.tts_method not in SAFE_TTS_METHODS:
            raise ValueError(
                f"tts_method '{self.config.tts_method}' requires task_df — "
                f"Shorts Creator only supports: {', '.join(SAFE_TTS_METHODS)}"
            )
        
        # Configure TTS voice
        if self.config.tts_method == 'edge_tts':
            update_key("edge_tts.voice", self.config.tts_voice)
        elif self.config.tts_method == 'azure_tts':
            update_key("azure_tts.voice", self.config.tts_voice)
        
        for i, segment in enumerate(segments):
            text = segment.get('text', '')
            if not text:
                continue
            
            filename = f"audio_{i:03d}.wav"
            filepath = os.path.join(audio_dir, filename)
            
            # Generate audio using VideoLingo's TTS
            tts_main(text, filepath, i, None)
            
            if os.path.exists(filepath):
                audio_files.append(filepath)
        
        return audio_files
    
    def _prepare_visuals(self, script_data: Dict) -> List[str]:
        """Prepare visual assets for the video."""
        visual_dir = os.path.join(self.config.output_dir, 'footage')
        # Create a persona-specific assets directory if it doesn't exist
        persona_assets_dir = None
        if script_data.get('title'):
            safe_title = "".join(c for c in script_data['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
            persona_assets_dir = os.path.join(self.config.output_dir, 'footage', 'persona_assets', safe_title)
            os.makedirs(persona_assets_dir, exist_ok=True)

        visual_files = []
        segments = script_data.get('segments', [])
        
        for i, segment in enumerate(segments):
            image_path = segment.get('image_path')
            
            # 1. Try local path (absolute or relative to project)
            if image_path:
                # Resolve path
                full_path = Path(image_path)
                if not full_path.is_absolute():
                    full_path = Path(os.getcwd()) / image_path
                
                if full_path.exists():
                    # Copy to persona assets if not already there
                    if persona_assets_dir:
                        dest_path = os.path.join(persona_assets_dir, full_path.name)
                        if not os.path.exists(dest_path) or os.path.getmtime(full_path) > os.path.getmtime(dest_path):
                            shutil.copy2(full_path, dest_path)
                        visual_files.append(dest_path)
                    else:
                        visual_files.append(str(full_path))
                    continue
                else:
                    print(f"⚠️  Warning: Local image not found at {full_path}. Falling back to AI/Stock.")
                
            visual_suggestion = segment.get('visual_suggestion', '')
            
            if not visual_suggestion:
                # Create generic visual suggestion from text
                visual_suggestion = f"Illustration for: {segment.get('text', '')[:50]}"
            
            try:
                # Try stock first if configured
                if self.config.prefer_stock:
                    images = self.footage_generator.search_stock_images(
                        visual_suggestion, 
                        per_page=1,
                        orientation='portrait'
                    )
                    if images:
                        image_path = self.footage_generator.download_stock_image(
                            images[0]['url'],
                            f"visual_{i:03d}.jpg"
                        )
                        visual_files.append(image_path)
                        continue
                
                # Generate with AI
                image_path = self.footage_generator.generate_image(
                    visual_suggestion,
                    style=self.config.image_style,
                    aspect_ratio=self.config.aspect_ratio
                )

                visual_files.append(image_path)
                
            except Exception as e:
                print(f"Warning: Failed to get visual for segment {i}: {e}")
                # Create a placeholder
                placeholder_path = self._create_placeholder_visual(i, visual_dir)
                visual_files.append(placeholder_path)
        
        return visual_files
    
    def _create_placeholder_visual(self, index: int, output_dir: str) -> str:
        """Create a simple placeholder visual."""
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a gradient background
        width, height = 1080, 1920
        img = Image.new('RGB', (width, height), color=(30, 30, 50))
        draw = ImageDraw.Draw(img)
        
        # Add simple gradient effect
        for y in range(height):
            r = int(30 + (y / height) * 30)
            g = int(30 + (y / height) * 20)
            b = int(50 + (y / height) * 30)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Add text
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
        except:
            font = ImageFont.load_default()
        
        text = f"Scene {index + 1}"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), text, fill=(200, 200, 200), font=font)
        
        # Save
        filepath = os.path.join(output_dir, f"placeholder_{index:03d}.png")
        img.save(filepath)
        
        return filepath
    
    def _assemble_video(self, script_data: Dict, 
                        audio_files: List[str],
                        visual_files: List[str]) -> str:
        """Assemble the final video."""
        safe_title = "".join(
            c for c in script_data.get('title', 'untitled')[:30] 
            if c.isalnum() or c in (' ', '-', '_')
        ).strip()
        
        filename = f"{safe_title}_{int(time.time())}.mp4"
        
        return self.video_assembler.assemble_video(
            script_data=script_data,
            audio_files=audio_files,
            visual_files=visual_files,
            output_filename=filename,
            add_captions=self.config.add_captions,
            background_music=self.config.background_music_path if self.config.add_background_music else None
        )


def quick_create_video(topic: str, duration: int = 60, 
                       style: str = 'educational') -> str:
    """Quick function to create a short video.
    
    Args:
        topic: Video topic
        duration: Target duration in seconds
        style: Content style
        
    Returns:
        Path to created video
    """
    config = WorkflowConfig(
        script_duration=duration,
        script_style=style
    )
    workflow = ShortsWorkflow(config)
    result = workflow.create_video(topic)
    return result.get('video_path')


if __name__ == '__main__':
    # Demo workflow
    print("=" * 60)
    print("Shorts Creator Workflow Demo")
    print("=" * 60)
    
    workflow = ShortsWorkflow()
    
    def progress(percent, message):
        print(f"[{percent:3d}%] {message}")
    
    topic = "3 productivity tips that actually work"
    
    print(f"\nCreating video about: {topic}")
    print("-" * 40)
    
    try:
        result = workflow.create_video(topic, progress_callback=progress)
        
        print("\n" + "=" * 60)
        print("VIDEO CREATED SUCCESSFULLY!")
        print("=" * 60)
        print(f"Video path: {result['video_path']}")
        print(f"Script saved: {result['files']['script']}")
        print(f"Steps completed: {result['steps_completed']}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
