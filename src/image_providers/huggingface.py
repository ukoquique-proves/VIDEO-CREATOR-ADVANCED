"""
HuggingFace Inference API Image Providers

FLUX and Stable Diffusion via HuggingFace Inference API.
Free tier available with rate limits (approximately 1000 requests/day for free accounts).
"""

import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

from src.image_providers.base import ImageProvider, ProviderResult, ProviderStatus


class HuggingFaceFluxProvider(ImageProvider):
    """
    FLUX.1-schnell via HuggingFace Inference API.
    
    Features:
    - Fast generation (4 steps)
    - Good quality for general use
    
    Requires:
    - HuggingFace API token (free tier available)
    """
    
    API_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__("huggingface_flux", config)
        self.api_key = api_key or (config.get('api_key') if config else None)
        self.timeout = config.get('timeout', 60) if config else 60
        self.max_retries = config.get('max_retries', 2) if config else 2
        self.retry_delay = config.get('retry_delay', 2) if config else 2
    
    def is_available(self) -> bool:
        """Check if provider has API key and is not rate limited."""
        if not self.api_key:
            return False
        return self.check_rate_limit_status()
    
    def generate(self, prompt: str, width: int = 1080, height: int = 1920,
                 output_dir: str = "output/generated",
                 **kwargs) -> ProviderResult:
        """Generate image using FLUX via HuggingFace."""
        if not self.is_available():
            return ProviderResult(
                success=False,
                error_message="No API key or rate limited",
                provider_name=self.name
            )
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_inference_steps": 4,
                "guidance_scale": 0
            }
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    # Success - save image
                    filename = f"flux_{int(time.time())}_{hash(prompt) % 10000}.png"
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
                    # Rate limited
                    self.mark_rate_limited(reset_time=time.time() + 300)  # 5 min wait
                    return ProviderResult(
                        success=False,
                        error_message="Rate limited (429)",
                        status_code=429,
                        provider_name=self.name
                    )
                
                elif response.status_code == 503:
                    # Model loading - HuggingFace loads models on demand
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * 2)  # Wait longer for model loading
                        continue
                    return ProviderResult(
                        success=False,
                        error_message="Model loading timeout",
                        status_code=503,
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
        
        return ProviderResult(
            success=False,
            error_message="All retries failed",
            provider_name=self.name
        )


class HuggingFaceSDProvider(ImageProvider):
    """
    Stable Diffusion XL via HuggingFace Inference API.
    """
    
    API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    
    def __init__(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__("huggingface_sdxl", config)
        self.api_key = api_key or (config.get('api_key') if config else None)
        self.timeout = config.get('timeout', 60) if config else 60
        self.max_retries = config.get('max_retries', 2) if config else 2
        self.retry_delay = config.get('retry_delay', 2) if config else 2
    
    def is_available(self) -> bool:
        if not self.api_key:
            return False
        return self.check_rate_limit_status()
    
    def generate(self, prompt: str, width: int = 1080, height: int = 1920,
                 output_dir: str = "output/generated",
                 **kwargs) -> ProviderResult:
        if not self.is_available():
            return ProviderResult(False, None, "No API key or rate limited", provider_name=self.name)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"inputs": prompt}
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.API_URL, headers=headers, json=payload, timeout=self.timeout)
                if response.status_code == 200:
                    filename = f"sdxl_{int(time.time())}_{hash(prompt) % 10000}.png"
                    file_path = output_path / filename
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    self.mark_success()
                    return ProviderResult(True, str(file_path), provider_name=self.name)
                elif response.status_code == 429:
                    self.mark_rate_limited(reset_time=time.time() + 300)
                    return ProviderResult(False, None, "Rate limited (429)", 429, self.name)
                elif response.status_code == 503:
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * 2)
                        continue
                    return ProviderResult(False, None, "Model loading timeout", 503, self.name)
                else:
                    self.mark_error()
                    return ProviderResult(False, None, f"HTTP {response.status_code}", response.status_code, self.name)
            except Exception as e:
                self.mark_error()
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                return ProviderResult(False, None, str(e), provider_name=self.name)
        
        return ProviderResult(False, None, "All retries failed", provider_name=self.name)
