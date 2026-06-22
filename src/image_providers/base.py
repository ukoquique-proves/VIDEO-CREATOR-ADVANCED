"""
Base interface for AI image generation providers.
Decoupled architecture allowing multiple providers with automatic failover.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class ProviderStatus(Enum):
    """Status of a provider."""
    AVAILABLE = "available"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


@dataclass
class ProviderResult:
    """Result from an image generation attempt."""
    success: bool
    image_path: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    provider_name: str = ""


class ImageProvider(ABC):
    """Abstract base class for image generation providers."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.status = ProviderStatus.AVAILABLE
        self.last_error_time: Optional[float] = None
        self.consecutive_errors = 0
        self.rate_limit_reset_time: Optional[float] = None
    
    @abstractmethod
    def generate(self, prompt: str, width: int = 1080, height: int = 1920, 
                 **kwargs) -> ProviderResult:
        """
        Generate an image from a text prompt.
        
        Args:
            prompt: Text description of the image
            width: Image width in pixels
            height: Image height in pixels
            **kwargs: Provider-specific options
            
        Returns:
            ProviderResult with success status and image path or error
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is currently available (not rate limited)."""
        pass
    
    def mark_rate_limited(self, reset_time: Optional[float] = None):
        """Mark this provider as rate limited."""
        self.status = ProviderStatus.RATE_LIMITED
        self.rate_limit_reset_time = reset_time
        self.last_error_time = time.time()
    
    def mark_error(self):
        """Mark this provider as having an error."""
        self.consecutive_errors += 1
        self.last_error_time = time.time()
        if self.consecutive_errors >= 3:
            self.status = ProviderStatus.ERROR
    
    def mark_success(self):
        """Reset error counter on success."""
        self.consecutive_errors = 0
        self.status = ProviderStatus.AVAILABLE
        self.rate_limit_reset_time = None
    
    def check_rate_limit_status(self) -> bool:
        """Check if rate limit has expired and provider is available again."""
        if self.status == ProviderStatus.RATE_LIMITED and self.rate_limit_reset_time:
            if time.time() >= self.rate_limit_reset_time:
                self.status = ProviderStatus.AVAILABLE
                self.rate_limit_reset_time = None
                return True
        return self.status == ProviderStatus.AVAILABLE
