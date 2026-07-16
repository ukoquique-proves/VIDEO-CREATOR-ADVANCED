"""
Provider Manager with Automatic Failover

Manages multiple image generation providers and automatically
switches to the next available provider when one fails or is rate-limited.
Includes cloud infrastructure detection to skip known-banned providers early.
Tracks provider performance metrics for observability and optimization.
"""

import time
import logging
import os
import concurrent.futures
from typing import List, Optional, Dict, Any
from pathlib import Path

from src.image_providers.base import ImageProvider, ProviderResult, ProviderStatus
from src.image_providers import cloud_detection
from src.image_providers.pollinations import PollinationsProvider
from src.image_providers.huggingface import HuggingFaceFluxProvider, HuggingFaceSDProvider
from src.image_providers.picsum import PicsumProvider
from src.image_providers.siliconflow import SiliconFlowProvider
from src.image_providers.cloudflare import CloudflareProvider

logger = logging.getLogger(__name__)

class ProviderManager:
    """
    Manages multiple AI image providers with automatic failover.
    Optionally tracks performance metrics for observability.
    """
    
    def __init__(self, output_dir: str = "output/generated", 
                 metrics_collector: Optional[Any] = None,
                 min_workers: Optional[int] = None,
                 max_workers: Optional[int] = None):
        self.providers: List[ImageProvider] = []
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_collector = metrics_collector  # Optional metrics for observability
        self._executor: Optional[concurrent.futures.ThreadPoolExecutor] = None
        self._executor_max_workers = 0
        self._hung_thread_count = 0
        
        # Read thread pool limits from environment variables or parameters
        self.min_workers = min_workers if min_workers is not None else \
            int(os.getenv("PROVIDER_MANAGER_MIN_WORKERS", "8"))
        self.max_workers = max_workers if max_workers is not None else \
            int(os.getenv("PROVIDER_MANAGER_MAX_WORKERS", "32"))

        # Detect cloud infrastructure and banned providers
        self.detector = cloud_detection.get_detector()
        if self.detector.is_cloud():
            cloud = self.detector.get_cloud_provider()
            banned = self.detector.get_banned_providers()
            logger.info(f"Running on {cloud.value} cloud infrastructure")
            if banned:
                logger.info(f"Providers banned on this infrastructure: {', '.join(banned)}")
        
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

    def _create_executor(self, max_workers: int) -> None:
        """Create a new shared executor, shutting down the previous one if needed."""
        if self._executor is not None:
            self._executor.shutdown(wait=False)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._executor_max_workers = max_workers

    def shutdown(self, wait: bool = True) -> None:
        """Shut down the shared thread pool used for provider attempts."""
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
            self._executor_max_workers = 0
        self._hung_thread_count = 0

    def generate_image(self, prompt: str, width: int = 1080, height: int = 1920,
                       style: str = "photorealistic", per_image_timeout: float = 120.0, **kwargs) -> ProviderResult:
        """
        Generate an image using available providers with automatic failover.
        Skips providers that are banned on current cloud infrastructure.

        Parameters
        ----------
        per_image_timeout : float
            Max seconds to wait for a single provider attempt before failing
            over to the next one. Prevents one slow provider from blocking
            the entire batch.
        """
        self.generation_count += 1
        
        # Enhance prompt with style
        enhanced_prompt = f"{prompt}, style: {style}"
        
        # Log skipped providers (banned on this infrastructure)
        for provider in self.providers:
            if provider.is_banned_on_infrastructure:
                logger.debug(f"Skipping {provider.name} (IP-blocked on this cloud infrastructure)")
        
        # Get available providers
        available = self.get_available_providers()
        
        if not available:
            # Try to reset rate-limited providers
            for provider in self.providers:
                provider.check_rate_limit_status()
            available = self.get_available_providers()
            
            if not available:
                # Build informative error message
                banned_providers = [p.name for p in self.providers if p.is_banned_on_infrastructure]
                if banned_providers:
                    # All available slots are banned on this infrastructure
                    cloud = self.detector.get_cloud_provider()
                    msg = f"All available providers are IP-blocked on {cloud.value} cloud infrastructure ({', '.join(banned_providers)})"
                else:
                    msg = "No providers available (all rate limited or no API keys)"
                return ProviderResult(
                    success=False,
                    error_message=msg,
                    provider_name="manager"
                )
        
        # Run each provider in a shared thread pool so timeouts do not block shutdown.
        # We purposely do not wait for threads to finish when a provider task times out,
        # because Python threads cannot be forcibly killed and a hanging provider should
        # not block failover to the next provider.
        desired_workers = max(self.min_workers, len(available) + 4, self._hung_thread_count + len(available) + 2)
        desired_workers = min(desired_workers, self.max_workers)
        logger.debug(f"Using thread pool with {desired_workers} workers (min: {self.min_workers}, max: {self.max_workers})")
        if self._executor is None or getattr(self._executor, '_shutdown', False) or desired_workers > self._executor_max_workers:
            self._create_executor(desired_workers)
        executor = self._executor
        last_error = None
        for i, provider in enumerate(available):
            logger.info(f"Trying provider {i+1}/{len(available)}: {provider.name}...")
            
            # Add small delay between providers to avoid overwhelming services
            if i > 0:
                time.sleep(0.5)
                self.failover_count += 1
            
            # Track timing for metrics
            attempt_start = time.time()

            future = executor.submit(
                provider.generate,
                enhanced_prompt,
                width=width,
                height=height,
                output_dir=str(self.output_dir),
                **kwargs,
            )
            try:
                result = future.result(timeout=per_image_timeout)
            except concurrent.futures.TimeoutError:
                logger.warning(
                    f"{provider.name} timed out after {per_image_timeout}s — trying next provider."
                )
                result = ProviderResult(
                    success=False,
                    error_message=f"Timed out after {per_image_timeout}s",
                    provider_name=provider.name,
                )
                cancelled = future.cancel()
                if not cancelled and future.running():
                    self._hung_thread_count += 1
            except Exception as exc:
                logger.warning(
                    f"{provider.name} failed with exception: {exc} — trying next provider."
                )
                result = ProviderResult(
                    success=False,
                    error_message=str(exc),
                    provider_name=provider.name,
                )

            attempt_duration_ms = (time.time() - attempt_start) * 1000

            if result.success:
                self.success_count += 1
                logger.info(f"Success with {provider.name}: {result.image_path}")
                
                # Track success in metrics
                if self.metrics_collector:
                    self.metrics_collector.track_provider_attempt(
                        provider.name, 
                        success=True, 
                        duration_ms=attempt_duration_ms
                    )
                return result
            else:
                logger.warning(f"Failed with {provider.name}: {result.error_message}")
                last_error = result
                
                # Track failure in metrics
                if self.metrics_collector:
                    self.metrics_collector.track_provider_attempt(
                        provider.name,
                        success=False,
                        duration_ms=attempt_duration_ms,
                        error=result.error_message
                    )
                
                # All failures fall through to the next provider. Rate-limited
                # providers do not require special handling here because the loop
                # already continues naturally after a failed attempt.

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
        Results are returned in the same order as the input prompts.
        Output filenames include a zero-padded sequence index to preserve
        sort order on disk (e.g. 001_, 002_, ...).
        """
        results = []
        
        for i, prompt in enumerate(prompts):
            logger.info(f"[{i+1}/{len(prompts)}] Generating: {prompt[:50]}...")
            
            result = self.generate_image(prompt, width, height, style)

            # Rename file to include zero-padded sequence index so that
            # alphabetical sort on disk matches generation order.
            if result.success and result.image_path:
                import os
                old_path = result.image_path
                directory = os.path.dirname(old_path)
                basename = os.path.basename(old_path)
                new_path = os.path.join(directory, f"{i+1:03d}_{basename}")
                try:
                    os.rename(old_path, new_path)
                    result = ProviderResult(
                        success=result.success,
                        image_path=new_path,
                        provider_name=result.provider_name,
                        status_code=result.status_code,
                        error_message=result.error_message,
                    )
                except OSError as exc:
                    logger.warning(
                        "Could not add sequence prefix to %s (keeping original path): %s",
                        old_path, exc,
                    )

            results.append(result)
            
            # Delay between generations to respect rate limits
            if i < len(prompts) - 1 and delay_between > 0:
                time.sleep(delay_between)
        
        # Summary
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Batch complete: {success_count}/{len(prompts)} successful")
        
        return results
