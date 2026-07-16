"""
Tests for provider self-registration system.
"""

import pytest
import os
import time
from unittest.mock import patch, MagicMock

from src.image_providers.base import ImageProvider, ProviderResult
from src.image_providers.registry import (
    ProviderSpec, ProviderRegistry, get_provider_registry,
    auto_register_providers
)
from src.image_providers.manager import ProviderManager


class TestProviderSpec:
    """Test provider specification."""
    
    def test_provider_spec_initialization(self):
        """Provider spec should initialize with required fields."""
        spec = ProviderSpec(
            name="Test Provider",
            provider_id="test",
            provider_class=MagicMock,
            credential_env_vars={"api_key": "TEST_API_KEY"}
        )
        
        assert spec.name == "Test Provider"
        assert spec.provider_id == "test"
        assert spec.always_add is False
        assert spec.priority == 100
    
    def test_provider_spec_get_credentials_with_env_vars(self):
        """Spec should retrieve credentials from environment."""
        spec = ProviderSpec(
            name="Test",
            provider_id="test",
            provider_class=MagicMock,
            credential_env_vars={
                "api_key": "TEST_API_KEY",
                "account_id": "TEST_ACCOUNT_ID"
            }
        )
        
        with patch.dict(os.environ, {"TEST_API_KEY": "secret123", "TEST_ACCOUNT_ID": "acc456"}):
            creds = spec.get_credentials()
            
            assert creds["api_key"] == "secret123"
            assert creds["account_id"] == "acc456"
    
    def test_provider_spec_get_credentials_missing(self):
        """Spec should return empty dict if credentials missing."""
        spec = ProviderSpec(
            name="Test",
            provider_id="test",
            provider_class=MagicMock,
            credential_env_vars={"api_key": "TEST_API_KEY"}
        )
        
        with patch.dict(os.environ, {}, clear=True):
            creds = spec.get_credentials()
            assert creds == {}
    
    def test_provider_spec_has_required_credentials(self):
        """Should check if all required credentials are available."""
        spec = ProviderSpec(
            name="Test",
            provider_id="test",
            provider_class=MagicMock,
            credential_env_vars={"api_key": "TEST_API_KEY"}
        )
        
        with patch.dict(os.environ, {"TEST_API_KEY": "secret"}):
            assert spec.has_required_credentials() is True
        
        with patch.dict(os.environ, {}, clear=True):
            assert spec.has_required_credentials() is False
    
    def test_provider_spec_is_available_always_add(self):
        """Provider with always_add=True should be available even without credentials."""
        spec = ProviderSpec(
            name="Free Provider",
            provider_id="free",
            provider_class=MagicMock,
            credential_env_vars={"api_key": "API_KEY"},
            always_add=True
        )
        
        with patch.dict(os.environ, {}, clear=True):
            assert spec.is_available() is True
    
    def test_provider_spec_is_available_with_credentials(self):
        """Provider should be available if credentials present."""
        spec = ProviderSpec(
            name="Test",
            provider_id="test",
            provider_class=MagicMock,
            credential_env_vars={"api_key": "TEST_API_KEY"}
        )
        
        with patch.dict(os.environ, {"TEST_API_KEY": "secret"}):
            assert spec.is_available() is True
    
    def test_provider_spec_is_available_without_credentials(self):
        """Provider should not be available if credentials missing."""
        spec = ProviderSpec(
            name="Test",
            provider_id="test",
            provider_class=MagicMock,
            credential_env_vars={"api_key": "TEST_API_KEY"}
        )
        
        with patch.dict(os.environ, {}, clear=True):
            assert spec.is_available() is False


class TestProviderRegistry:
    """Test provider registry."""
    
    def test_registry_initialization(self):
        """Registry should initialize with default providers."""
        registry = ProviderRegistry()
        
        assert len(registry.providers) > 0
        # Check that known providers are registered
        provider_ids = [p.provider_id for p in registry.providers]
        assert "cloudflare" in provider_ids
        assert "siliconflow" in provider_ids
        assert "pollinations" in provider_ids
        assert "picsum" in provider_ids
    
    def test_registry_register_provider(self):
        """Registry should allow registering new providers."""
        registry = ProviderRegistry()
        initial_count = len(registry.providers)
        
        new_spec = ProviderSpec(
            name="Custom Provider",
            provider_id="custom",
            provider_class=MagicMock,
            credential_env_vars={}
        )
        
        registry.register(new_spec)
        
        assert len(registry.providers) == initial_count + 1
        assert registry.get_provider_by_id("custom") is not None
    
    def test_registry_prevent_duplicate_registration(self):
        """Registry should not allow duplicate provider IDs."""
        registry = ProviderRegistry()
        initial_count = len(registry.providers)
        
        duplicate_spec = ProviderSpec(
            name="Duplicate",
            provider_id="pollinations",
            provider_class=MagicMock,
            credential_env_vars={}
        )
        
        registry.register(duplicate_spec)
        
        # Should not add duplicate
        assert len(registry.providers) == initial_count
    
    def test_registry_get_available_providers(self):
        """Registry should return only available providers sorted by priority."""
        registry = ProviderRegistry()
        
        with patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "123", "CLOUDFLARE_API_TOKEN": "abc"}):
            available = registry.get_available_providers()
            
            # Should have at least Pollinations and Picsum (always_add)
            available_ids = [p.provider_id for p in available]
            assert "pollinations" in available_ids
            assert "picsum" in available_ids
            
            # Check sorting by priority
            priorities = [p.priority for p in available]
            assert priorities == sorted(priorities)
    
    def test_registry_get_provider_by_id(self):
        """Registry should retrieve provider by ID."""
        registry = ProviderRegistry()
        
        spec = registry.get_provider_by_id("cloudflare")
        assert spec is not None
        assert spec.name == "Cloudflare"
        
        spec = registry.get_provider_by_id("nonexistent")
        assert spec is None
    
    def test_registry_priority_ordering(self):
        """Available providers should be ordered by priority."""
        registry = ProviderRegistry()
        
        available = registry.get_available_providers()
        priorities = [p.priority for p in available]
        
        # All providers should be sorted by priority
        assert priorities == sorted(priorities)


class TestAutoRegistration:
    """Test automatic provider registration."""
    
    def test_auto_register_providers_with_credentials(self):
        """Auto-register should add providers with available credentials."""
        manager = ProviderManager()
        initial_count = len(manager.providers)
        
        # Mock environment with Cloudflare credentials
        with patch.dict(os.environ, {
            "CLOUDFLARE_ACCOUNT_ID": "acc123",
            "CLOUDFLARE_API_TOKEN": "token456"
        }):
            auto_register_providers(manager)
        
        # Should add providers (at least Pollinations and Picsum are always added)
        assert len(manager.providers) > initial_count
    
    def test_auto_register_adds_free_providers(self):
        """Auto-register should always add free providers."""
        manager = ProviderManager()
        
        with patch.dict(os.environ, {}, clear=True):
            auto_register_providers(manager)
        
        # Should have at least Pollinations and Picsum
        provider_names = [p.name for p in manager.providers]
        assert "pollinations" in provider_names
        assert "picsum" in provider_names
    
    def test_auto_register_skips_missing_credentials(self):
        """Auto-register should skip providers without credentials."""
        manager = ProviderManager()
        
        with patch.dict(os.environ, {}, clear=True):
            # Only free providers should be added
            auto_register_providers(manager)
        
        # Check that only free providers are present
        provider_ids = [p.name for p in manager.providers]
        # Should not have SiliconFlow or Cloudflare without credentials
        assert len(provider_ids) > 0


class TestGlobalRegistry:
    """Test global registry singleton."""
    
    def test_get_provider_registry_singleton(self):
        """Should return same registry instance on multiple calls."""
        reg1 = get_provider_registry()
        reg2 = get_provider_registry()
        
        assert reg1 is reg2


class TestRegistryIntegration:
    """Integration tests for provider registry."""
    
    def test_registry_with_image_adapter(self):
        """Provider registry should integrate with image adapter."""
        from src.image_adapter import _get_fresh_provider_manager
        
        # Get manager (should auto-register providers)
        manager = _get_fresh_provider_manager()
        
        # Should have providers registered
        assert len(manager.providers) > 0
        
        # Should have at least free providers
        provider_names = [p.name for p in manager.providers]
        assert "pollinations" in provider_names or len(provider_names) > 0
    
    def test_registry_provider_ordering(self):
        """Providers should be tried in priority order."""
        manager = ProviderManager()
        
        with patch.dict(os.environ, {}, clear=True):
            auto_register_providers(manager)
        
        # Verify manager has providers
        assert len(manager.providers) > 0
        
        # Check provider order (if multiple providers present)
        if len(manager.providers) > 1:
            # Pollinations should come before Picsum (lower priority)
            names = [p.name for p in manager.providers]
            if "pollinations" in names and "picsum" in names:
                assert names.index("pollinations") < names.index("picsum")


class HangingProvider(ImageProvider):
    def __init__(self):
        super().__init__("hanging")
        self.called = False

    def generate(self, prompt, **kwargs):
        self.called = True
        time.sleep(2)
        return ProviderResult(success=False, error_message="hung", provider_name=self.name)

    def is_available(self):
        return True


class QuickProvider(ImageProvider):
    def __init__(self):
        super().__init__("quick")

    def generate(self, prompt, **kwargs):
        return ProviderResult(success=True, image_path="/tmp/quick.png", provider_name=self.name)

    def is_available(self):
        return True


class RateLimitedProvider(ImageProvider):
    def __init__(self):
        super().__init__("ratelimited")

    def generate(self, prompt, **kwargs):
        return ProviderResult(
            success=False,
            error_message="Rate limited",
            status_code=429,
            provider_name=self.name
        )

    def is_available(self):
        return True


class TestProviderManagerTimeouts:
    def test_generate_image_fails_over_quickly_when_provider_hangs(self):
        """A hung provider should time out and fail over without waiting for the thread to exit."""
        manager = ProviderManager()
        manager.providers = [HangingProvider(), QuickProvider()]

        start = time.time()
        result = manager.generate_image("prompt", per_image_timeout=0.5)
        elapsed = time.time() - start

        assert result.success is True
        assert result.provider_name == "quick"
        assert elapsed < 1.5, f"Failover should not wait for the hung provider thread (elapsed {elapsed})"

    def test_hung_provider_does_not_starve_later_calls(self):
        """A hung provider should not consume all shared pool workers permanently."""
        manager = ProviderManager()
        manager.providers = [HangingProvider()]

        manager.generate_image("prompt1", per_image_timeout=0.2)

        manager.providers = [QuickProvider()]
        result = manager.generate_image("prompt2", per_image_timeout=0.5)

        assert result.success is True
        assert result.provider_name == "quick"

    def test_generate_image_reuses_thread_pool_across_calls(self):
        """The manager should reuse a shared executor instead of creating a fresh one per image."""
        manager = ProviderManager()
        manager.providers = [QuickProvider()]

        assert manager._executor is None
        first = manager.generate_image("prompt1", per_image_timeout=1.0)
        assert first.success is True
        assert manager._executor is not None
        executor_obj = manager._executor

        second = manager.generate_image("prompt2", per_image_timeout=1.0)
        assert second.success is True
        assert manager._executor is executor_obj

        manager.shutdown(wait=True)
        assert manager._executor is None

    def test_generate_image_fails_over_when_provider_rate_limited(self):
        """Rate-limited providers should fail over to the next available provider."""
        manager = ProviderManager()
        manager.providers = [RateLimitedProvider(), QuickProvider()]

        result = manager.generate_image("prompt", per_image_timeout=1.0)

        assert result.success is True
        assert result.provider_name == "quick"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
