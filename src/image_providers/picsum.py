"""
Picsum Image Provider

Fallback provider using Lorem Picsum to guarantee image generation success.
Useful for testing or when AI providers fail.
"""

import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from src.image_providers.base import ImageProvider, ProviderResult, ProviderStatus

class PicsumProvider(ImageProvider):
    """
    Fallback provider using Lorem Picsum to guarantee image generation success.
    """
    
    BASE_URL = "https://picsum.photos/"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("picsum", config)
        self.timeout = config.get('timeout', 30) if config else 30
        
    def is_available(self) -> bool:
        """Picsum is generally always available without rate limits."""
        return self.check_rate_limit_status()
        
    def generate(self, prompt: str, width: int = 1080, height: int = 1920,
                 output_dir: str = "output/generated",
                 **kwargs) -> ProviderResult:
        """
        Fetch a random image from Picsum.
        """
        if not self.is_available():
            return ProviderResult(False, None, "Provider rate limited", provider_name=self.name)
            
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Use a seed to ensure some variety but consistency if needed
        # URL format: https://picsum.photos/seed/{seed}/{width}/{height}
        seed = hash(prompt) % 10000
        url = f"{self.BASE_URL}seed/{seed}/{width}/{height}"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            if response.status_code == 200:
                filename = f"picsum_{int(time.time())}_{seed}.jpg"
                file_path = output_path / filename
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                    
                self.mark_success()
                
                return ProviderResult(
                    success=True, 
                    image_path=str(file_path),
                    provider_name=self.name
                )
            else:
                self.mark_error()
                return ProviderResult(
                    success=False, 
                    error_message=f"HTTP {response.status_code}",
                    status_code=response.status_code,
                    provider_name=self.name
                )
        except Exception as e:
            self.mark_error()
            return ProviderResult(
                success=False, 
                error_message=str(e),
                provider_name=self.name
            )
