"""
Pollinations.ai Image Provider

Free AI image generation with no API key required.
Rate limits apply but generous for free tier.
"""

import time
import random
import requests
from pathlib import Path
from typing import Optional

from .base import ImageProvider, ProviderResult, ProviderStatus


class PollinationsProvider(ImageProvider):
    """
    Pollinations.ai provider - completely free, no API key needed.
    
    Features:
    - No authentication required
    - Supports various aspect ratios
    - Fast generation (usually 5-15 seconds)
    
    Limitations:
    - Rate limited (exact limits not documented)
    - May timeout on complex prompts
    """
    
    BASE_URL = "https://image.pollinations.ai/prompt/"
    
    def __init__(self, config: dict = None):
        super().__init__("pollinations", config)
        self.timeout = config.get('timeout', 60) if config else 60
        self.max_retries = config.get('max_retries', 2) if config else 2
        self.retry_delay = config.get('retry_delay', 1) if config else 1
    
    def is_available(self) -> bool:
        """Check if provider is available (not rate limited)."""
        return self.check_rate_limit_status()
    
    def generate(self, prompt: str, width: int = 1080, height: int = 1920,
                 output_dir: str = "output/shorts/footage/generated",
                 **kwargs) -> ProviderResult:
        """
        Generate image using Pollinations.ai.
        
        Args:
            prompt: Image description
            width: Image width (default 1080 for TikTok/Reels)
            height: Image height (default 1920 for TikTok/Reels)
            output_dir: Directory to save generated image
            
        Returns:
            ProviderResult with success status and image path
        """
        if not self.is_available():
            return ProviderResult(
                success=False,
                error_message=f"Provider {self.name} is rate limited",
                provider_name=self.name
            )
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Build enhanced prompt with dimensions
        enhanced_prompt = f"{prompt}, {width}x{height}"
        encoded_prompt = requests.utils.quote(enhanced_prompt)
        
        # Build URL with parameters
        url = f"{self.BASE_URL}{encoded_prompt}?width={width}&height={height}&nologo=true&seed={random.randint(1, 99999)}"
        
        # Try with retries
        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, timeout=self.timeout)
                
                if response.status_code == 200:
                    # Success - save image
                    filename = f"pollinations_{int(time.time())}_{random.randint(1000,9999)}.png"
                    file_path = output_path / filename
                    
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    self.mark_success()
                    
                    return ProviderResult(
                        success=True,
                        image_path=str(file_path),
                        provider_name=self.name
                    )
                
                elif response.status_code == 429:
                    # Rate limited - mark and retry
                    self.mark_rate_limited(reset_time=time.time() + 60)
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    else:
                        return ProviderResult(
                            success=False,
                            error_message=f"Rate limited (429)",
                            status_code=429,
                            provider_name=self.name
                        )
                
                else:
                    # Other error
                    self.mark_error()
                    return ProviderResult(
                        success=False,
                        error_message=f"HTTP {response.status_code}",
                        status_code=response.status_code,
                        provider_name=self.name
                    )
                    
            except requests.exceptions.Timeout:
                self.mark_error()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return ProviderResult(
                    success=False,
                    error_message="Request timeout",
                    provider_name=self.name
                )
                
            except Exception as e:
                self.mark_error()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return ProviderResult(
                    success=False,
                    error_message=str(e),
                    provider_name=self.name
                )
        
        # All retries exhausted
        return ProviderResult(
            success=False,
            error_message="All retries failed",
            provider_name=self.name
        )
