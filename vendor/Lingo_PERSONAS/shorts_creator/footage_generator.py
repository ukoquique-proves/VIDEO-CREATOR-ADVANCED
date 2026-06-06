"""
Footage Generator for Short-Form Videos

Handles:
- Stock footage search and download (Pexels, Pixabay, etc.)
- AI image generation (Flux, Stable Diffusion via free APIs)
- Visual asset management
"""

import os
import json
import requests
import time
import random
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Free API endpoints for image generation
FREE_IMAGE_APIS = {
    'pollinations': 'https://image.pollinations.ai/prompt/',  # Free, no API key
    'flux_huggingface': 'https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell',
    'stable_diffusion': 'https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0',
}

# Stock footage APIs (free tiers available)
STOCK_APIS = {
    'pexels': {
        'base_url': 'https://api.pexels.com/videos/search',
        'image_url': 'https://api.pexels.com/v1/search',
        'requires_key': True,
    },
    'pixabay': {
        'base_url': 'https://pixabay.com/api/videos/',
        'image_url': 'https://pixabay.com/api/',
        'requires_key': True,
    },
    'pexels_free': {
        'base_url': 'https://images.pexels.com',
        'requires_key': False,
        'note': 'Direct image access for demo purposes'
    }
}


class FootageGenerator:
    """Generate and fetch visual assets for short-form videos."""
    
    def __init__(self, output_dir: str = 'output/footage', 
                 pexels_key: str = None, pixabay_key: str = None,
                 huggingface_key: str = None):
        """Initialize the footage generator.
        
        Args:
            output_dir: Directory to save downloaded/generated assets
            pexels_key: Pexels API key (optional, has free tier)
            pixabay_key: Pixabay API key (optional, has free tier)
            huggingface_key: HuggingFace API key for SD/Flux (optional, has free tier)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.pexels_key = pexels_key or os.environ.get('PEXELS_API_KEY', '')
        self.pixabay_key = pixabay_key or os.environ.get('PIXABAY_API_KEY', '')
        self.huggingface_key = huggingface_key or os.environ.get('HUGGINGFACE_API_KEY', '')
        
        # Create subdirectories
        (self.output_dir / 'stock').mkdir(exist_ok=True)
        (self.output_dir / 'generated').mkdir(exist_ok=True)
        (self.output_dir / 'cached').mkdir(exist_ok=True)
    
    def search_stock_videos(self, query: str, per_page: int = 10,
                            orientation: str = 'portrait') -> List[Dict]:
        """Search for stock videos.
        
        Args:
            query: Search query
            per_page: Number of results
            orientation: 'portrait', 'landscape', or 'square'
            
        Returns:
            List of video results with metadata
        """
        results = []
        
        # Try Pexels first
        if self.pexels_key:
            pexels_results = self._search_pexels_videos(query, per_page, orientation)
            results.extend(pexels_results)
        
        # Try Pixabay as backup
        if self.pixabay_key and len(results) < per_page:
            pixabay_results = self._search_pixabay_videos(query, per_page - len(results))
            results.extend(pixabay_results)
        
        return results[:per_page]
    
    def search_stock_images(self, query: str, per_page: int = 10,
                           orientation: str = 'portrait') -> List[Dict]:
        """Search for stock images.
        
        Args:
            query: Search query
            per_page: Number of results
            orientation: 'portrait', 'landscape', or 'square'
            
        Returns:
            List of image results with metadata
        """
        results = []
        
        if self.pexels_key:
            pexels_results = self._search_pexels_images(query, per_page, orientation)
            results.extend(pexels_results)
        
        if self.pixabay_key and len(results) < per_page:
            pixabay_results = self._search_pixabay_images(query, per_page - len(results))
            results.extend(pixabay_results)
        
        return results[:per_page]
    
    def download_stock_video(self, video_url: str, filename: str = None) -> str:
        """Download a stock video.
        
        Args:
            video_url: URL of the video
            filename: Custom filename (auto-generated if None)
            
        Returns:
            Path to downloaded file
        """
        if not filename:
            filename = f"stock_video_{int(time.time())}.mp4"
        
        output_path = self.output_dir / 'stock' / filename
        
        response = requests.get(video_url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(output_path)
        
        raise Exception(f"Failed to download video: {response.status_code}")
    
    def download_stock_image(self, image_url: str, filename: str = None) -> str:
        """Download a stock image.
        
        Args:
            image_url: URL of the image
            filename: Custom filename (auto-generated if None)
            
        Returns:
            Path to downloaded file
        """
        if not filename:
            filename = f"stock_image_{int(time.time())}.jpg"
        
        output_path = self.output_dir / 'stock' / filename
        
        response = requests.get(image_url, stream=True, timeout=30)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return str(output_path)
        
        raise Exception(f"Failed to download image: {response.status_code}")
    
    def generate_image(self, prompt: str, style: str = 'photorealistic',
                       engine: str = 'pollinations', 
                       aspect_ratio: str = '9:16') -> str:
        """Generate an image using AI.
        
        Args:
            prompt: Image description
            style: Style preset (photorealistic, artistic, cartoon, etc.)
            engine: Generation engine ('pollinations', 'flux', 'sd')
            aspect_ratio: Target aspect ratio ('9:16', '16:9', '1:1')
            
        Returns:
            Path to generated image
        """
        # Enhance prompt with style
        enhanced_prompt = self._enhance_image_prompt(prompt, style, aspect_ratio)
        
        if engine == 'pollinations':
            return self._generate_pollinations(enhanced_prompt, aspect_ratio)
        elif engine == 'flux' and self.huggingface_key:
            return self._generate_flux(enhanced_prompt)
        elif engine == 'sd' and self.huggingface_key:
            return self._generate_stable_diffusion(enhanced_prompt)
        else:
            # Default to pollinations (free, no API key needed)
            return self._generate_pollinations(enhanced_prompt, aspect_ratio)
    
    def generate_image_series(self, prompts: List[str], style: str = 'photorealistic',
                              engine: str = 'pollinations') -> List[str]:
        """Generate multiple images for a video.
        
        Args:
            prompts: List of image descriptions
            style: Style for all images
            engine: Generation engine
            
        Returns:
            List of paths to generated images
        """
        paths = []
        for i, prompt in enumerate(prompts):
            path = self.generate_image(prompt, style, engine)
            paths.append(path)
            # Small delay to avoid rate limiting
            time.sleep(0.5)
        return paths
    
    def get_visuals_for_script(self, script_segments: List[Dict],
                               prefer_stock: bool = True) -> List[Dict]:
        """Get appropriate visuals for each script segment.
        
        Args:
            script_segments: List of script segments with visual_suggestions
            prefer_stock: Prefer stock footage over AI-generated
            
        Returns:
            List of segments with attached visual paths
        """
        result_segments = []
        
        for segment in script_segments:
            visual_suggestion = segment.get('visual_suggestion', '')
            segment_result = segment.copy()
            
            if prefer_stock and (self.pexels_key or self.pixabay_key):
                # Try stock first
                images = self.search_stock_images(visual_suggestion, per_page=3)
                if images:
                    try:
                        image_path = self.download_stock_image(images[0]['url'])
                        segment_result['visual_path'] = image_path
                        segment_result['visual_type'] = 'stock'
                    except Exception:
                        pass
            
            # If no stock found, generate with AI
            if 'visual_path' not in segment_result:
                try:
                    image_path = self.generate_image(visual_suggestion)
                    segment_result['visual_path'] = image_path
                    segment_result['visual_type'] = 'generated'
                except Exception as e:
                    segment_result['visual_error'] = str(e)
            
            result_segments.append(segment_result)
        
        return result_segments
    
    def _search_pexels_videos(self, query: str, per_page: int, 
                              orientation: str) -> List[Dict]:
        """Search Pexels for videos."""
        try:
            headers = {'Authorization': self.pexels_key}
            params = {
                'query': query,
                'per_page': per_page,
                'orientation': orientation
            }
            
            response = requests.get(
                STOCK_APIS['pexels']['base_url'],
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for video in data.get('videos', []):
                    # Get the medium quality video file
                    video_files = video.get('video_files', [])
                    video_url = None
                    for vf in video_files:
                        if vf.get('quality') == 'hd':
                            video_url = vf.get('link')
                            break
                    if not video_url and video_files:
                        video_url = video_files[0].get('link')
                    
                    if video_url:
                        results.append({
                            'id': video.get('id'),
                            'url': video_url,
                            'thumbnail': video.get('image', ''),
                            'duration': video.get('duration', 0),
                            'source': 'pexels',
                            'photographer': video.get('user', {}).get('name', '')
                        })
                return results
        except Exception as e:
            print(f"Pexels video search error: {e}")
        return []
    
    def _search_pexels_images(self, query: str, per_page: int,
                              orientation: str) -> List[Dict]:
        """Search Pexels for images."""
        try:
            headers = {'Authorization': self.pexels_key}
            params = {
                'query': query,
                'per_page': per_page,
                'orientation': orientation
            }
            
            response = requests.get(
                STOCK_APIS['pexels']['image_url'],
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for photo in data.get('photos', []):
                    # Get portrait size for TikTok/Reels
                    src = photo.get('src', {})
                    image_url = src.get('portrait') or src.get('large') or src.get('original')
                    
                    if image_url:
                        results.append({
                            'id': photo.get('id'),
                            'url': image_url,
                            'thumbnail': src.get('tiny', ''),
                            'source': 'pexels',
                            'photographer': photo.get('photographer', '')
                        })
                return results
        except Exception as e:
            print(f"Pexels image search error: {e}")
        return []
    
    def _search_pixabay_videos(self, query: str, per_page: int) -> List[Dict]:
        """Search Pixabay for videos."""
        try:
            params = {
                'key': self.pixabay_key,
                'q': query,
                'per_page': per_page,
                'video_type': 'all'
            }
            
            response = requests.get(
                STOCK_APIS['pixabay']['base_url'],
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for hit in data.get('hits', []):
                    videos = hit.get('videos', {})
                    # Get medium quality
                    video_data = videos.get('medium', videos.get('small', {}))
                    
                    results.append({
                        'id': hit.get('id'),
                        'url': video_data.get('url', ''),
                        'thumbnail': hit.get('picture', ''),
                        'duration': hit.get('duration', 0),
                        'source': 'pixabay',
                        'user': hit.get('user', '')
                    })
                return results
        except Exception as e:
            print(f"Pixabay video search error: {e}")
        return []
    
    def _search_pixabay_images(self, query: str, per_page: int) -> List[Dict]:
        """Search Pixabay for images."""
        try:
            params = {
                'key': self.pixabay_key,
                'q': query,
                'per_page': per_page,
                'image_type': 'photo'
            }
            
            response = requests.get(
                STOCK_APIS['pixabay']['image_url'],
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for hit in data.get('hits', []):
                    results.append({
                        'id': hit.get('id'),
                        'url': hit.get('largeImageURL', hit.get('webformatURL', '')),
                        'thumbnail': hit.get('previewURL', ''),
                        'source': 'pixabay',
                        'user': hit.get('user', '')
                    })
                return results
        except Exception as e:
            print(f"Pixabay image search error: {e}")
        return []
    
    def _generate_pollinations(self, prompt: str, aspect_ratio: str) -> str:
        """Generate image using Pollinations.ai (free, no API key)."""
        # Add aspect ratio to prompt
        size_map = {
            '9:16': '1080x1920',  # TikTok/Reels
            '16:9': '1920x1080',  # YouTube
            '1:1': '1080x1080',   # Square
        }
        size = size_map.get(aspect_ratio, '1080x1920')
        
        # Build URL
        encoded_prompt = requests.utils.quote(f"{prompt}, {size}")
        url = f"{FREE_IMAGE_APIS['pollinations']}{encoded_prompt}?width={size.split('x')[0]}&height={size.split('x')[1]}&nologo=true"
        
        # Download the generated image
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            filename = f"generated_{int(time.time())}_{random.randint(1000,9999)}.png"
            output_path = self.output_dir / 'generated' / filename
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return str(output_path)
        
        raise Exception(f"Pollinations generation failed: {response.status_code}")
    
    def _generate_flux(self, prompt: str) -> str:
        """Generate image using FLUX via HuggingFace API."""
        headers = {"Authorization": f"Bearer {self.huggingface_key}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_inference_steps": 4,  # FLUX schnell is fast
                "guidance_scale": 0
            }
        }
        
        response = requests.post(
            FREE_IMAGE_APIS['flux_huggingface'],
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            filename = f"flux_{int(time.time())}.png"
            output_path = self.output_dir / 'generated' / filename
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return str(output_path)
        
        raise Exception(f"FLUX generation failed: {response.status_code}")
    
    def _generate_stable_diffusion(self, prompt: str) -> str:
        """Generate image using Stable Diffusion XL via HuggingFace API."""
        headers = {"Authorization": f"Bearer {self.huggingface_key}"}
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "negative_prompt": "blurry, bad quality, distorted",
                "num_inference_steps": 20,
                "guidance_scale": 7.5
            }
        }
        
        response = requests.post(
            FREE_IMAGE_APIS['stable_diffusion'],
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            filename = f"sd_{int(time.time())}.png"
            output_path = self.output_dir / 'generated' / filename
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            return str(output_path)
        
        raise Exception(f"SD generation failed: {response.status_code}")
    
    def _enhance_image_prompt(self, prompt: str, style: str, 
                              aspect_ratio: str) -> str:
        """Enhance the image prompt with style and quality modifiers."""
        style_modifiers = {
            'photorealistic': 'photorealistic, high quality photography, professional lighting, sharp focus, 8k',
            'cinematic': 'cinematic, dramatic lighting, movie still, color graded, atmospheric',
            'artistic': 'artistic, stylized, beautiful composition, creative',
            'cartoon': 'cartoon style, animated, vibrant colors, clean lines',
            'minimal': 'minimalist, clean, simple, modern, elegant',
            'dramatic': 'dramatic, high contrast, intense, powerful',
            'corporate': 'professional, business, clean, modern office setting'
        }
        
        modifier = style_modifiers.get(style, style_modifiers['photorealistic'])
        
        # Add aspect ratio context
        if aspect_ratio == '9:16':
            modifier += ', vertical composition, mobile optimized'
        
        return f"{prompt}, {modifier}"


# Convenience functions
def get_stock_image(query: str, api_key: str = None) -> str:
    """Quick function to get a stock image."""
    gen = FootageGenerator(pexels_key=api_key)
    results = gen.search_stock_images(query, per_page=1)
    if results:
        return gen.download_stock_image(results[0]['url'])
    return None


def generate_ai_image(prompt: str, style: str = 'photorealistic') -> str:
    """Quick function to generate an AI image (free via Pollinations)."""
    gen = FootageGenerator()
    return gen.generate_image(prompt, style, engine='pollinations')


if __name__ == '__main__':
    # Test the footage generator
    gen = FootageGenerator()
    
    print("Testing AI image generation (free via Pollinations)...")
    image_path = gen.generate_image(
        "A person working productively at a modern desk with laptop",
        style="photorealistic",
        aspect_ratio="9:16"
    )
    print(f"Generated image: {image_path}")
