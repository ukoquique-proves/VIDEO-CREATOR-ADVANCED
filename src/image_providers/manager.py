"""
Provider Manager with Automatic Failover

Manages multiple image generation providers and automatically
switches to the next available provider when one fails or is rate-limited.
"""

import time
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from src.image_providers.base import ImageProvider, ProviderResult, ProviderStatus
from src.image_providers.pollinations import PollinationsProvider
from src.image_providers.huggingface import HuggingFaceFluxProvider, HuggingFaceSDProvider
from src.image_providers.picsum import PicsumProvider
from src.image_providers.siliconflow import SiliconFlowProvider
from src.image_providers.cloudflare import CloudflareProvider

logger = logging.getLogger(__name__)

class ProviderManager:
    """
    Manages multiple AI image providers with automatic failover.
    """
    
    def __init__(self, output_dir: str = "output/generated"):
        self.providers: List[ImageProvider] = []
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Track usage statistics
        self.generation_count = 0
        self.success_count = 0
        self.failover_count = 0
    
    def add_pollinations(self, config: Optional[Dict[str, Any]] = None):
        """Add Pollinations.ai provider (free, no API key)."""
        self.providers.append(PollinationsProvider(config))
        logger.info("Added Pollinations provider")
    
    def add_cloudflare(self, account_id: Optional[str] = None, api_token: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Add Cloudflare Workers AI provider."""
        if account_id and api_token:
            self.providers.append(CloudflareProvider(account_id, api_token, config))
            logger.info("Added Cloudflare Workers AI provider")
        else:
            logger.warning("Skipped Cloudflare (missing account_id or api_token)")
    
    def add_siliconflow(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Add SiliconFlow provider."""
        if api_key:
            self.providers.append(SiliconFlowProvider(api_key, config))
            logger.info("Added SiliconFlow provider")
        else:
            logger.warning("Skipped SiliconFlow (no API key)")
    
    def add_huggingface_flux(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Add HuggingFace FLUX provider."""
        if api_key:
            self.providers.append(HuggingFaceFluxProvider(api_key, config))
            logger.info("Added HuggingFace FLUX provider")
        else:
            logger.warning("Skipped HuggingFace FLUX (no API key)")
    
    def add_huggingface_sd(self, api_key: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Add HuggingFace SDXL provider."""
        if api_key:
            self.providers.append(HuggingFaceSDProvider(api_key, config))
            logger.info("Added HuggingFace SDXL provider")
        else:
            logger.warning("Skipped HuggingFace SDXL (no API key)")
            
    def add_picsum(self, config: Optional[Dict[str, Any]] = None):
        """Add Picsum provider (fallback)."""
        self.providers.append(PicsumProvider(config))
        logger.info("Added Picsum provider")
    
    def add_provider(self, provider: ImageProvider):
        """Add a custom provider instance."""
        self.providers.append(provider)
        logger.info(f"Added custom provider: {provider.name}")
    
    def get_available_providers(self) -> List[ImageProvider]:
        """Get list of currently available providers."""
        available = []
        for provider in self.providers:
            if provider.is_available():
                available.append(provider)
        return available
    
    def generate_image(self, prompt: str, width: int = 1080, height: int = 1920,
                       style: str = "photorealistic", **kwargs) -> ProviderResult:
        """
        Generate an image using available providers with automatic failover.
        """
        self.generation_count += 1
        
        # Enhance prompt with style
        enhanced_prompt = f"{prompt}, style: {style}"
        
        # Get available providers
        available = self.get_available_providers()
        
        if not available:
            # Try to reset rate-limited providers
            for provider in self.providers:
                provider.check_rate_limit_status()
            available = self.get_available_providers()
            
            if not available:
                return ProviderResult(
                    success=False,
                    error_message="No providers available (all rate limited or no API keys)",
                    provider_name="manager"
                )
        
        # Try each available provider
        last_error = None
        for i, provider in enumerate(available):
            logger.info(f"Trying provider {i+1}/{len(available)}: {provider.name}...")
            
            # Add small delay between providers to avoid overwhelming services
            if i > 0:
                time.sleep(0.5)
                self.failover_count += 1
            
            result = provider.generate(
                enhanced_prompt, 
                width=width, 
                height=height,
                output_dir=str(self.output_dir),
                **kwargs
            )
            
            if result.success:
                self.success_count += 1
                logger.info(f"Success with {provider.name}: {result.image_path}")
                return result
            else:
                logger.warning(f"Failed with {provider.name}: {result.error_message}")
                last_error = result
                
                # If rate limited, continue to next provider immediately
                if result.status_code == 429:
                    continue
        
        # All providers failed
        return ProviderResult(
            success=False,
            error_message=f"All providers failed. Last error: {last_error.error_message if last_error else 'Unknown'}",
            provider_name="manager",
            status_code=last_error.status_code if last_error else None
        )
    
    def generate_images_batch(self, prompts: List[str], width: int = 1080, 
                              height: int = 1920, style: str = "photorealistic",
                              delay_between: float = 1.0) -> List[ProviderResult]:
        """
        Generate multiple images with automatic failover for each.
        """
        results = []
        
        for i, prompt in enumerate(prompts):
            logger.info(f"[{i+1}/{len(prompts)}] Generating: {prompt[:50]}...")
            
            result = self.generate_image(prompt, width, height, style)
            results.append(result)
            
            # Delay between generations to respect rate limits
            if i < len(prompts) - 1 and delay_between > 0:
                time.sleep(delay_between)
        
        # Summary
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Batch complete: {success_count}/{len(prompts)} successful")
        
        return results
