"""
AI Script Generator for Short-Form Videos

Generates engaging scripts for TikTok/Reels/YouTube Shorts style videos.
Uses LLM API to create scripts with proper pacing and hooks.
"""

import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils import load_key, ask_gpt


class ScriptGenerator:
    """Generate scripts for short-form videos using AI."""
    
    # Script templates for different content types
    TEMPLATES = {
        'educational': 'Educational content that teaches something new in 60 seconds',
        'entertainment': 'Fun, engaging content that entertains and captures attention',
        'motivational': 'Inspiring content that motivates and uplifts',
        'storytelling': 'Narrative content that tells a compelling story',
        'listicle': 'List-based content (e.g., "5 tips for...", "Top 3 ways to...")',
        'how_to': 'Tutorial content showing how to do something',
        'facts': 'Interesting facts or trivia content',
        'news': 'Breaking news or trending topic commentary',
    }
    
    def __init__(self, api_key=None, base_url=None, model=None):
        """Initialize the script generator.
        
        Args:
            api_key: API key for LLM (uses config if not provided)
            base_url: Base URL for LLM API (uses config if not provided)
            model: Model name (uses config if not provided)
        """
        self.api_key = api_key or load_key("api.key")
        self.base_url = base_url or load_key("api.base_url")
        self.model = model or load_key("api.model")
    
    def generate_script(self, topic: str, style: str = 'educational', 
                        duration: int = 60, tone: str = 'casual',
                        hook_type: str = 'question', target_audience: str = 'general',
                        language: str = 'English') -> dict:
        """Generate a complete script for a short-form video.
        
        Args:
            topic: The main topic/subject of the video
            style: Content style (educational, entertainment, etc.)
            duration: Target duration in seconds (15, 30, 60)
            tone: Tone of voice (casual, professional, humorous, dramatic)
            hook_type: Type of opening hook (question, statement, story, fact)
            target_audience: Target audience description
            language: Language for the script
            
        Returns:
            dict with script segments, full text, and metadata
        """
        prompt = self._build_script_prompt(topic, style, duration, tone, 
                                           hook_type, target_audience, language)
        
        response = ask_gpt(prompt, resp_type='json', log_title='script_generation')
        
        if response:
            return self._parse_script_response(response, topic, style, duration)
        return None
    
    def generate_script_series(self, main_topic: str, num_videos: int = 5,
                               style: str = 'educational', duration: int = 60) -> list:
        """Generate a series of related scripts.
        
        Args:
            main_topic: The overarching topic for the series
            num_videos: Number of scripts to generate
            style: Content style
            duration: Target duration per video
            
        Returns:
            List of script dicts
        """
        prompt = self._build_series_prompt(main_topic, num_videos, style, duration)
        
        response = ask_gpt(prompt, resp_type='json', log_title='script_series')
        
        if response and 'scripts' in response:
            return [
                self._parse_script_response(script, main_topic, style, duration)
                for script in response['scripts']
            ]
        return []
    
    def enhance_script(self, script: str, improvement: str = 'engagement') -> dict:
        """Enhance an existing script.
        
        Args:
            script: The original script text
            improvement: Type of improvement (engagement, clarity, humor, emotion)
            
        Returns:
            Enhanced script dict
        """
        prompt = self._build_enhance_prompt(script, improvement)
        
        response = ask_gpt(prompt, resp_type='json', log_title='script_enhance')
        
        if response:
            return {
                'original': script,
                'enhanced': response.get('enhanced_script', script),
                'changes': response.get('changes_made', []),
                'tips': response.get('delivery_tips', [])
            }
        return {'original': script, 'enhanced': script, 'changes': [], 'tips': []}
    
    def _build_script_prompt(self, topic, style, duration, tone, 
                             hook_type, target_audience, language):
        """Build the prompt for script generation."""
        
        # Calculate approximate word count based on duration
        # Average speaking rate: 130-150 words per minute
        words_per_second = 2.3
        target_words = int(duration * words_per_second)
        
        return f'''
## Role
You are an expert short-form video scriptwriter specializing in {style} content for TikTok, Instagram Reels, and YouTube Shorts. You understand viral content mechanics, audience retention, and engagement optimization.

## Task
Write a compelling {duration}-second video script about "{topic}".

## Requirements
1. **Target Duration**: {duration} seconds (~{target_words} words)
2. **Style**: {self.TEMPLATES.get(style, style)}
3. **Tone**: {tone}
4. **Language**: {language}
5. **Target Audience**: {target_audience}
6. **Hook Type**: {hook_type} (must capture attention in first 2 seconds)

## Script Structure
- **Hook** (0-3s): Attention-grabbing opening that stops the scroll
- **Setup** (3-10s): Context or problem setup
- **Content** (10-{duration-5}s): Main value delivery
- **CTA** ({duration-5}-{duration}s): Strong call-to-action

## Output Format
Return ONLY valid JSON with this structure:
```json
{{
    "title": "Catchy video title (under 60 chars)",
    "hook": "The opening line that grabs attention",
    "segments": [
        {{
            "text": "Segment text",
            "duration_estimate": 5,
            "visual_suggestion": "What should appear on screen",
            "emphasis": "key word or phrase to emphasize"
        }}
    ],
    "full_script": "Complete script as one text block",
    "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"],
    "delivery_tips": ["Tip for voiceover delivery"],
    "visual_notes": "General visual direction for the video"
}}
```

## Important Notes
- Make every word count - short-form requires efficiency
- Include a pattern interrupt every 10-15 seconds
- Use conversational language, avoid formal speech
- End with a clear, actionable CTA
- Consider text overlay suggestions for key points

Note: Start your answer with ```json and end with ```, do not add any other text.
'''.strip()
    
    def _build_series_prompt(self, main_topic, num_videos, style, duration):
        """Build prompt for generating a series of scripts."""
        return f'''
## Role
You are an expert short-form video content strategist who creates cohesive video series.

## Task
Create a {num_videos}-video series about "{main_topic}" for {style} content.

## Requirements
1. Each video: {duration} seconds
2. Style: {style}
3. Videos should be standalone but form a cohesive series
4. Progressive complexity or related subtopics
5. Each video should reference the series (e.g., "Part 3 of 5")

## Output Format
```json
{{
    "series_title": "Name for the series",
    "series_description": "Brief description of the series arc",
    "scripts": [
        {{
            "title": "Video title",
            "hook": "Opening hook",
            "segments": [
                {{
                    "text": "Segment text",
                    "duration_estimate": 5,
                    "visual_suggestion": "On-screen visual",
                    "emphasis": "Key emphasis"
                }}
            ],
            "full_script": "Complete script",
            "hashtags": ["#tags"],
            "part_number": 1
        }}
    ]
}}
```

Note: Start your answer with ```json and end with ```, do not add any other text.
'''.strip()
    
    def _build_enhance_prompt(self, script, improvement):
        """Build prompt for script enhancement."""
        return f'''
## Role
You are a short-form video script optimization expert.

## Task
Enhance this script for better {improvement}.

## Original Script
{script}

## Enhancement Focus: {improvement}
{self._get_improvement_guidance(improvement)}

## Output Format
```json
{{
    "enhanced_script": "The improved full script",
    "changes_made": ["List of specific changes"],
    "delivery_tips": ["Tips for better delivery"]
}}
```

Note: Start your answer with ```json and end with ```, do not add any other text.
'''.strip()
    
    def _get_improvement_guidance(self, improvement):
        """Get specific guidance for improvement type."""
        guidance = {
            'engagement': '''
- Add stronger hook in first 2 seconds
- Include pattern interrupts
- Add questions or interactive elements
- Create curiosity gaps
- Use power words and emotional triggers''',
            'clarity': '''
- Simplify complex language
- Remove filler words
- Improve logical flow
- Add transitions between ideas
- Make key points more memorable''',
            'humor': '''
- Add relatable observations
- Include unexpected twists
- Use callback references
- Add self-deprecating elements
- Time punchlines effectively''',
            'emotion': '''
- Add personal story elements
- Use sensory language
- Create emotional peaks
- Build tension and release
- End with emotional resonance'''
        }
        return guidance.get(improvement, 'Improve overall quality and impact')
    
    def _parse_script_response(self, response, topic, style, duration):
        """Parse and structure the script response."""
        return {
            'topic': topic,
            'style': style,
            'target_duration': duration,
            'title': response.get('title', topic),
            'hook': response.get('hook', ''),
            'segments': response.get('segments', []),
            'full_script': response.get('full_script', ''),
            'hashtags': response.get('hashtags', []),
            'delivery_tips': response.get('delivery_tips', []),
            'visual_notes': response.get('visual_notes', ''),
            'metadata': {
                'word_count': len(response.get('full_script', '').split()),
                'segment_count': len(response.get('segments', []))
            }
        }


def generate_quick_script(topic: str, duration: int = 60) -> dict:
    """Convenience function for quick script generation."""
    generator = ScriptGenerator()
    return generator.generate_script(topic, duration=duration)


if __name__ == '__main__':
    # Test script generation
    generator = ScriptGenerator()
    
    print("Testing script generation...")
    result = generator.generate_script(
        topic="The science of productivity",
        style="educational",
        duration=60,
        tone="casual"
    )
    
    if result:
        print(f"\nTitle: {result['title']}")
        print(f"Full Script:\n{result['full_script']}")
        print(f"\nHashtags: {result['hashtags']}")
