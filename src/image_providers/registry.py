"""
Provider Registry & Auto-Registration System

Defines all available image providers and their credential requirements.
Providers auto-register based on available credentials (environment variables or config).

This replaces hardcoded provider initialization with a declarative, configuration-driven system
that makes it easy to add new providers and understand what's available.
"""

import os
import logging
from typing import Dict, Any, Optional, Type, Callable, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProviderSpec:
    """Specification for an image provider."""
    name: str  # Display name (e.g., "Cloudflare")
    provider_id: str  # Internal ID (e.g., "cloudflare")
    provider_class: Type  # The provider class to instantiate
    credential_env_vars: Dict[str, str]  # {param_name: env_var_name} for required credentials
    optional_env_vars: Dict[str, str] = None  # {param_name: env_var_name} for optional credentials
    always_add: bool = False  # If True, add even without credentials (e.g., free providers like Picsum, Pollinations)
    priority: int = 100  # Lower number = higher priority (used for ordering)
    
    def __post_init__(self):
        if self.optional_env_vars is None:
            self.optional_env_vars = {}
    
    def get_credentials(self) -> Dict[str, Any]:
        """Get credentials from environment variables."""
        credentials = {}
        
        # Check required credentials
        for param_name, env_var_name in self.credential_env_vars.items():
            value = os.getenv(env_var_name)
            if value:
                credentials[param_name] = value
        
        # Check optional credentials
        for param_name, env_var_name in self.optional_env_vars.items():
            value = os.getenv(env_var_name)
            if value:
                credentials[param_name] = value
        
        return credentials
    
    def has_required_credentials(self) -> bool:
        """Check if all required credentials are available."""
        return bool(self.get_credentials() or not self.credential_env_vars)
    
    def is_available(self) -> bool:
        """Check if this provider should be added."""
        if self.always_add:
            return True
        return self.has_required_credentials()


class ProviderRegistry:
    """Registry of all available image providers."""
    
    def __init__(self):
        """Initialize provider registry with all known providers."""
        self.providers: List[ProviderSpec] = []
        self._register_default_providers()
    
    def _register_default_providers(self):
        """Register all built-in providers."""
        from src.image_providers.cloudflare import CloudflareProvider
        from src.image_providers.siliconflow import SiliconFlowProvider
        from src.image_providers.huggingface import HuggingFaceFluxProvider, HuggingFaceSDProvider
        from src.image_providers.pollinations import PollinationsProvider
        from src.image_providers.picsum import PicsumProvider
        
        # Cloudflare Workers AI
        self.register(ProviderSpec(
            name="Cloudflare",
            provider_id="cloudflare",
            provider_class=CloudflareProvider,
            credential_env_vars={
                "account_id": "CLOUDFLARE_ACCOUNT_ID",
                "api_token": "CLOUDFLARE_API_TOKEN",
            },
            priority=10  # Highest priority
        ))
        
        # SiliconFlow
        self.register(ProviderSpec(
            name="SiliconFlow",
            provider_id="siliconflow",
            provider_class=SiliconFlowProvider,
            credential_env_vars={
                "api_key": "SILICONFLOW_API_KEY",
            },
            priority=20
        ))
        
        # Pollinations (free, always available)
        self.register(ProviderSpec(
            name="Pollinations",
            provider_id="pollinations",
            provider_class=PollinationsProvider,
            credential_env_vars={},
            always_add=True,
            priority=30
        ))
        
        # HuggingFace FLUX
        self.register(ProviderSpec(
            name="HuggingFace FLUX",
            provider_id="huggingface_flux",
            provider_class=HuggingFaceFluxProvider,
            credential_env_vars={
                "api_key": "HUGGINGFACE_API_KEY",
            },
            priority=40
        ))
        
        # HuggingFace SDXL
        self.register(ProviderSpec(
            name="HuggingFace SDXL",
            provider_id="huggingface_sd",
            provider_class=HuggingFaceSDProvider,
            credential_env_vars={
                "api_key": "HUGGINGFACE_API_KEY",
            },
            priority=50
        ))
        
        # Picsum (free, always available)
        self.register(ProviderSpec(
            name="Picsum",
            provider_id="picsum",
            provider_class=PicsumProvider,
            credential_env_vars={},
            always_add=True,
            priority=100  # Lowest priority (fallback)
        ))
    
    def register(self, spec: ProviderSpec):
        """Register a new provider spec."""
        # Check if already registered by ID
        if any(p.provider_id == spec.provider_id for p in self.providers):
            logger.warning(f"Provider {spec.provider_id} already registered")
            return
        
        self.providers.append(spec)
        logger.debug(f"Registered provider: {spec.name} ({spec.provider_id})")
    
    def get_available_providers(self) -> List[ProviderSpec]:
        """Get all providers that should be added (sorted by priority)."""
        available = [p for p in self.providers if p.is_available()]
        available.sort(key=lambda p: p.priority)
        return available
    
    def get_provider_by_id(self, provider_id: str) -> Optional[ProviderSpec]:
        """Get a specific provider by ID."""
        for p in self.providers:
            if p.provider_id == provider_id:
                return p
        return None
    
    def log_provider_status(self):
        """Log which providers are available and which are missing credentials."""
        logger.info("=" * 60)
        logger.info("Image Provider Registry Status")
        logger.info("=" * 60)
        
        available = self.get_available_providers()
        unavailable = [p for p in self.providers if not p.is_available()]
        
        logger.info(f"Available providers ({len(available)}):")
        for spec in available:
            if spec.always_add:
                logger.info(f"  ✓ {spec.name} ({spec.provider_id}) [always available]")
            else:
                creds = list(spec.credential_env_vars.keys())
                logger.info(f"  ✓ {spec.name} ({spec.provider_id}) [credentials: {', '.join(creds)}]")
        
        if unavailable:
            logger.info(f"\nUnavailable providers ({len(unavailable)}) — missing credentials:")
            for spec in unavailable:
                required = list(spec.credential_env_vars.keys())
                missing = [env_var for env_var in spec.credential_env_vars.values() 
                          if not os.getenv(env_var)]
                logger.info(f"  ✗ {spec.name} ({spec.provider_id})")
                logger.info(f"    Required: {', '.join(required)}")
                logger.info(f"    Missing env vars: {', '.join(missing)}")
        
        logger.info("=" * 60)


# Global registry instance
_registry: Optional[ProviderRegistry] = None


def get_provider_registry() -> ProviderRegistry:
    """Get or create the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def auto_register_providers(manager) -> None:
    """Auto-register all available providers in the manager."""
    registry = get_provider_registry()
    
    logger.debug("Auto-registering providers based on available credentials...")
    
    available = registry.get_available_providers()
    
    for spec in available:
        try:
            credentials = spec.get_credentials()
            
            if not credentials and spec.always_add:
                # Free provider, no credentials needed
                manager.add_provider(spec.provider_class())
                logger.info(f"Registered {spec.name} (free provider)")
            elif credentials:
                # Has required credentials
                manager.add_provider(spec.provider_class(**credentials))
                logger.info(f"Registered {spec.name}")
            else:
                logger.debug(f"Skipped {spec.name} (missing credentials)")
        
        except Exception as e:
            logger.warning(f"Failed to register {spec.name}: {e}")
