"""
Video Assembler for Short-Form Videos

Assembles final TikTok/Reels/YouTube Shorts style videos from:
- Script segments
- Voiceover audio
- Visual assets (stock footage or AI-generated images)
- Background music
- Text overlays and captions
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

# MoviePy v2 imports
from moviepy import (
    VideoFileClip, AudioFileClip, ImageClip, TextClip, 
    CompositeVideoClip, CompositeAudioClip, concatenate_videoclips, concatenate_audioclips
)
from moviepy.video.fx import Resize, Crop, FadeIn, FadeOut
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut, MultiplyVolume

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class VideoConfig:
    """Configuration for short-form video output."""
    width: int = 1080
    height: int = 1920

    fps: int = 30
    audio_fps: int = 44100
    bitrate: str = '8000k'
    
    # Text settings
    font: str = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    font_size: int = 36
    font_color: str = 'white'
    stroke_color: str = 'black'
    stroke_width: int = 2
    
    # Animation settings
    image_duration: float = 3.0
    transition_duration: float = 0.3
    fade_duration: float = 0.5
    
    # Caption settings
    caption_position: str = 'bottom'
    caption_margin: int = 200


class VideoAssembler:
    """Assemble short-form videos from components."""
    
    def __init__(self, output_dir: str = 'output', config: VideoConfig = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or VideoConfig()
        (self.output_dir / 'temp').mkdir(exist_ok=True)
        (self.output_dir / 'final').mkdir(exist_ok=True)
    
    def assemble_video(self, 
                       script_data: Dict,
                       audio_files: List[str],
                       visual_files: List[str],
                       background_music: str = None,
                       output_filename: str = None,
                       add_captions: bool = True,
                       add_watermark: bool = False,
                       watermark_text: str = None) -> str:
        """Assemble a complete short-form video."""
        if not output_filename:
            output_filename = f"shorts_video_{script_data.get('title', 'untitled')[:30]}.mp4"
        
        output_path = self.output_dir / 'final' / output_filename
        
        # Process audio
        full_audio = self._combine_audio(audio_files)
        total_duration = full_audio.duration
        
        # Create video clips from visuals
        video_clips = self._create_visual_sequence(
            visual_files, total_duration, script_data.get('segments', [])
        )
        
        # Add captions
        if add_captions and script_data.get('segments'):
            video_clips = self._add_captions(video_clips, script_data['segments'])
        
        # Combine clips
        final_video = concatenate_videoclips(video_clips, method='compose')
        
        # Add background music
        if background_music and os.path.exists(background_music):
            final_video = self._add_background_music(final_video, background_music)
        
        # Set audio
        final_video = final_video.with_audio(full_audio)
        
        # Add watermark
        if add_watermark:
            final_video = self._add_watermark(final_video, watermark_text)
        
        # Export
        final_video.write_videofile(
            str(output_path),
            fps=self.config.fps,
            codec='libx264',
            audio_codec='aac',
            bitrate=self.config.bitrate,
            threads=4,
            preset='medium'
        )
        
        final_video.close()
        full_audio.close()
        
        return str(output_path)
    
    def create_simple_video(self,
                            script_text: str,
                            audio_path: str,
                            visuals: List[str],
                            output_path: str = None) -> str:
        """Create a simple video from text, audio, and visuals."""
        if not output_path:
            output_path = str(self.output_dir / 'final' / f'quick_video_{int(time.time())}.mp4')
        
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        time_per_visual = duration / len(visuals)
        
        clips = [self._create_clip_from_file(v, time_per_visual) for v in visuals]
        video = concatenate_videoclips(clips, method='compose').with_audio(audio)
        
        video.write_videofile(output_path, fps=self.config.fps, codec='libx264', audio_codec='aac')
        
        video.close()
        audio.close()
        
        return output_path
    
    def add_text_overlay(self,
                         video_path: str,
                         text: str,
                         position: str = 'bottom',
                         duration: float = None,
                         font_size: int = None,
                         output_path: str = None) -> str:
        """Add text overlay to existing video."""
        if not output_path:
            output_path = str(self.output_dir / 'final' / f'text_overlay_{int(time.time())}.mp4')
        
        video = VideoFileClip(video_path)
        duration = duration or video.duration
        font_size = font_size or self.config.font_size
        
        txt_clip = TextClip(
            text=text, font=self.config.font, font_size=font_size, color=self.config.font_color,
            stroke_color=self.config.stroke_color, stroke_width=self.config.stroke_width,
            method='caption', size=(self.config.width - 100, None), text_align='center'
        ).with_duration(duration)
        
        # Position
        if position == 'bottom':
            pos = ('center', self.config.height - self.config.caption_margin - txt_clip.h)
        elif position == 'top':
            pos = ('center', self.config.caption_margin)
        else:
            pos = 'center'
        txt_clip = txt_clip.with_position(pos)
        
        final = CompositeVideoClip([video, txt_clip])
        final.write_videofile(output_path, fps=self.config.fps, codec='libx264', audio_codec='aac')
        
        final.close()
        video.close()
        
        return output_path
    
    def _combine_audio(self, audio_files: List[str]) -> AudioFileClip:
        """Combine multiple audio files into one."""
        audio_clips = [AudioFileClip(f) for f in audio_files if os.path.exists(f)]
        if not audio_clips:
            raise ValueError("No valid audio files provided")
        return concatenate_audioclips(audio_clips)
    
    def _create_visual_sequence(self, visual_files: List[str], total_duration: float,
                                segments: List[Dict] = None) -> List:
        """Create a sequence of video clips from visual files."""
        clips = []
        
        if segments:
            durations = [seg.get('duration_estimate', self.config.image_duration) for seg in segments]
            total_segment_duration = sum(durations)
            if total_segment_duration > 0:
                scale = total_duration / total_segment_duration
                durations = [d * scale for d in durations]
        else:
            time_per_visual = total_duration / max(len(visual_files), 1)
            durations = [time_per_visual] * len(visual_files)
        
        for i, visual_path in enumerate(visual_files):
            if i >= len(durations):
                break
            clips.append(self._create_clip_from_file(visual_path, durations[i]))
        
        # Extend last clip if needed
        if clips:
            current_duration = sum(c.duration for c in clips)
            if current_duration < total_duration:
                clips[-1] = self._create_clip_from_file(visual_files[-1], total_duration - current_duration + clips[-1].duration)
        
        return clips
    
    def _create_clip_from_file(self, file_path: str, duration: float):
        """Create a video clip from an image or video file."""
        file_path = str(file_path)
        
        if file_path.endswith(('.mp4', '.mov', '.avi', '.webm')):
            # Strip any embedded audio from source clips so the pipeline's
            # narration/mix audio is the single authoritative audio track.
            clip = VideoFileClip(file_path).without_audio()
            clip = self._resize_to_aspect_ratio(clip)

            if clip.duration < duration:
                # Loop by concatenating (clips have no audio, safe to repeat)
                loops_needed = int(duration / clip.duration) + 1
                clip = concatenate_videoclips([clip] * loops_needed).subclipped(0, duration)
            else:
                clip = clip.subclipped(0, duration)
        else:
            clip = ImageClip(file_path).with_duration(duration)
            clip = self._resize_to_aspect_ratio(clip)

        
        # Add fade effects
        clip = clip.with_effects([FadeIn(self.config.fade_duration), FadeOut(self.config.fade_duration)])
        
        return clip
    
    def _resize_to_aspect_ratio(self, clip):
        """Resize clip to target aspect ratio (Portrait or Landscape) with Center Crop."""
        target_w = self.config.width
        target_h = self.config.height
        target_ratio = target_w / target_h
        current_ratio = clip.w / clip.h
        
        if current_ratio > target_ratio:
            # Source is wider than target - fit to height, then crop sides
            clip = clip.with_effects([Resize(height=target_h)])
            # New width is target_h * current_ratio. Crop to target_w.
            new_w = clip.w
            x_offset = (new_w - target_w) / 2
            clip = clip.with_effects([Crop(
                x1=int(x_offset), y1=0,
                x2=int(x_offset + target_w), y2=target_h
            )])
        else:
            # Source is taller than target (or matches) - fit to width, then crop top/bottom
            clip = clip.with_effects([Resize(width=target_w)])
            # New height is target_w / current_ratio. Crop to target_h.
            new_h = clip.h
            y_offset = (new_h - target_h) / 2
            clip = clip.with_effects([Crop(
                x1=0, y1=int(y_offset),
                x2=target_w, y2=int(y_offset + target_h)
            )])
        
        return clip
    
    def _add_captions(self, clips: List, segments: List[Dict]) -> List:
        """Add text captions to video clips."""
        captioned_clips = []
        
        for i, clip in enumerate(clips):
            if i < len(segments) and segments[i].get('text'):
                # Split text into chunks of max 8 words for better readability and timing
                full_text = segments[i]['text']
                words = full_text.split()
                chunk_size = 8
                text_chunks = [" ".join(words[j:j + chunk_size]) for j in range(0, len(words), chunk_size)]
                
                if len(text_chunks) > 1:
                    # Create a sequence of text clips for this segment
                    chunk_duration = clip.duration / len(text_chunks)
                    txt_clips = []
                    for j, chunk in enumerate(text_chunks):
                        txt = TextClip(
                            text=chunk, font=self.config.font,
                            font_size=self.config.font_size,
                            color=self.config.font_color, stroke_color=self.config.stroke_color,
                            stroke_width=self.config.stroke_width, method='caption',
                            size=(self.config.width - 200, None), text_align='center'
                        ).with_duration(chunk_duration).with_start(j * chunk_duration)
                        
                        txt = txt.with_position(
                            ('center', self.config.height - self.config.caption_margin - txt.h)
                        )
                        txt_clips.append(txt)
                    
                    clip = CompositeVideoClip([clip] + txt_clips)
                else:
                    # Single chunk
                    txt = TextClip(
                        text=full_text, font=self.config.font,
                        font_size=self.config.font_size,
                        color=self.config.font_color, stroke_color=self.config.stroke_color,
                        stroke_width=self.config.stroke_width, method='caption',
                        size=(self.config.width - 200, None), text_align='center'
                    ).with_duration(clip.duration)
                    txt = txt.with_position(
                        ('center', self.config.height - self.config.caption_margin - txt.h)
                    )
                    clip = CompositeVideoClip([clip, txt])
                    
            captioned_clips.append(clip)
        
        return captioned_clips
    
    def _add_background_music(self, video, music_path: str, volume: float = 0.3):
        """Add background music to video."""
        music = AudioFileClip(music_path)
        
        if music.duration < video.duration:
            loops_needed = int(video.duration / music.duration) + 1
            music = concatenate_audioclips([music] * loops_needed).subclipped(0, video.duration)
        else:
            music = music.subclipped(0, video.duration)
        
        music = music.with_effects([AudioFadeIn(1), AudioFadeOut(2), MultiplyVolume(volume)])
        
        final_audio = CompositeAudioClip([video.audio, music]) if video.audio else music
        return video.with_audio(final_audio)
    
    def _add_watermark(self, video, text: str = None):
        """Add watermark to video."""
        text = text or "Created with VideoLingo"
        watermark = TextClip(
            text=text, font=self.config.font, font_size=24, color='white',
            stroke_color='black', stroke_width=1
        ).with_duration(video.duration).with_position(('right', 'bottom'))
        
        return CompositeVideoClip([video, watermark])


def create_shorts_video(script_data: Dict, audio_dir: str, visual_dir: str, 
                        output_path: str = None) -> str:
    """Convenience function to create a shorts video."""
    assembler = VideoAssembler()
    
    audio_files = sorted([os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith(('.wav', '.mp3'))])
    visual_files = sorted([os.path.join(visual_dir, f) for f in os.listdir(visual_dir) if f.endswith(('.jpg', '.png', '.mp4'))])
    
    return assembler.assemble_video(script_data, audio_files, visual_files)


if __name__ == '__main__':
    print("VideoAssembler module loaded (MoviePy v2)")
    print(f"Config: {VideoConfig()}")
