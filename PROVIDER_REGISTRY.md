# Provider Self-Registration System

## Overview

This feature replaces hardcoded provider initialization with a **configuration-driven, self-registering system**. Providers automatically register themselves based on available credentials, making it easy to add new providers and understand which ones are available on the current system.

## Architecture

### Core Components

#### 1. **ProviderSpec** — Provider Specification
Defines everything needed to know about a provider:
```python
@dataclass
class ProviderSpec:
    name: str                                  # Display name
    provider_id: str                          # Internal ID
    provider_class: Type                      # The provider class
    credential_env_vars: Dict[str, str]       # Required credentials
    optional_env_vars: Dict[str, str]         # Optional credentials
    always_add: bool                          # Add even without credentials?
    priority: int                             # Sort order (lower = higher priority)
```

#### 2. **ProviderRegistry** — Central Registry
Manages all provider specifications and determines which are available:
```python
registry = ProviderRegistry()

# Get providers that should be used (with credentials or free)
available = registry.get_available_providers()

# Log status (for debugging)
registry.log_provider_status()
```

#### 3. **Auto-Registration Function**
Automatically instantiates and registers available providers:
```python
from src.image_providers.registry import auto_register_providers

manager = ProviderManager()
auto_register_providers(manager)  # Registers all available providers
```

## Benefits

### 1. **Declarative Configuration**
Instead of hardcoded calls:
```python
# ❌ Old way (hardcoded)
manager.add_cloudflare(os.getenv("CLOUDFLARE_ACCOUNT_ID"), ...)
manager.add_siliconflow(os.getenv("SILICONFLOW_API_KEY"))
manager.add_pollinations()
# ... more hardcoded calls
```

We now have:
```python
# ✅ New way (declarative registry)
auto_register_providers(manager)  # One line!
```

### 2. **Easy to Add New Providers**
Adding a new provider just requires updating the registry:
```python
registry.register(ProviderSpec(
    name="MyNewProvider",
    provider_id="mynew",
    provider_class=MyNewProvider,
    credential_env_vars={"api_key": "MYNEW_API_KEY"},
    priority=25  # Between SiliconFlow and Pollinations
))
```

### 3. **Clear Visibility**
Log provider status at startup:
```
============================================================
Image Provider Registry Status
============================================================
Available providers (3):
  ✓ Cloudflare (cloudflare) [credentials: account_id, api_token]
  ✓ Pollinations (pollinations) [always available]
  ✓ Picsum (picsum) [always available]

Unavailable providers (2) — missing credentials:
  ✗ SiliconFlow (siliconflow)
    Required: api_key
    Missing env vars: SILICONFLOW_API_KEY
  ✗ HuggingFace FLUX (huggingface_flux)
    Required: api_key
    Missing env vars: HUGGINGFACE_API_KEY
============================================================
```

### 4. **Automatic Priority Ordering**
Providers are tried in priority order:
1. Cloudflare (priority 10) — fastest
2. SiliconFlow (priority 20)
3. Pollinations (priority 30)
4. HuggingFace FLUX (priority 40)
5. HuggingFace SDXL (priority 50)
6. Picsum (priority 100) — slowest (fallback)

### 5. **Scalable and Maintainable**
All provider definitions in one place (`registry.py`):
- Easy to review provider priorities
- Easy to add/remove providers
- Easy to understand credential requirements
- Reduce coupling between providers and adapter

## Current Providers

| Provider | ID | Priority | Credentials | Always? |
|----------|----|-----------|----|---------|
| Cloudflare | `cloudflare` | 10 | account_id, api_token | ✗ |
| SiliconFlow | `siliconflow` | 20 | api_key | ✗ |
| Pollinations | `pollinations` | 30 | none | ✓ |
| HuggingFace FLUX | `huggingface_flux` | 40 | api_key | ✗ |
| HuggingFace SDXL | `huggingface_sd` | 50 | api_key | ✗ |
| Picsum | `picsum` | 100 | none | ✓ |

## Planned Providers (Not Implemented)

The following providers are referenced in various docs or UI dropdowns but are not wired into the native provider library in this release. Do not set `image_engine` to these values — `src/image_adapter.py` will reject them and the registry will not instantiate them.

- Unsplash — `unsplash` (planned, not implemented)
- Pexels — `pexels` (planned, not implemented)
- Pixabay — `pixabay` (planned, not implemented)

## Usage

### Basic Usage (Automatic)
```python
from src.image_adapter import _get_fresh_provider_manager

# Just call this - providers auto-register
manager = _get_fresh_provider_manager()

# Provider status is logged at startup:
# INFO - Registered Cloudflare
# INFO - Registered Pollinations (free provider)
# INFO - Registered Picsum (free provider)
# WARNING - Missing SiliconFlow credentials
```

### Advanced: Custom Provider Registration
```python
from src.image_providers.registry import get_provider_registry

registry = get_provider_registry()

# Register a new custom provider
registry.register(ProviderSpec(
    name="Custom AI",
    provider_id="custom_ai",
    provider_class=CustomAIProvider,
    credential_env_vars={"api_key": "CUSTOM_API_KEY"},
    priority=15  # Try before Pollinations
))

# Create a fresh manager, and auto-register all (including custom)
manager = _get_fresh_provider_manager(registry=registry)
```

### Checking Registry Status
```python
from src.image_providers.registry import get_provider_registry

registry = get_provider_registry()

# Get all available providers
available = registry.get_available_providers()
for spec in available:
    print(f"Will use: {spec.name}")

# Log full status
registry.log_provider_status()
```

## Implementation Details

### Environment Variables
Credentials are read from environment variables defined in `.env`:
```bash
# .env file
CLOUDFLARE_ACCOUNT_ID=my-account-id
CLOUDFLARE_API_TOKEN=my-token
SILICONFLOW_API_KEY=my-key
HUGGINGFACE_API_KEY=my-hf-token
```

### How It Works

```
1. ProviderRegistry initialized
   └─ Registers all built-in providers with specs
      (credentials, priority, always_add flag)

2. _get_fresh_provider_manager() called
   └─ Creates a **fresh, new ProviderManager** for each generation
   └─ Calls auto_register_providers(manager)
      └─ Gets all available providers from registry
         (checks credentials from environment)
      └─ Instantiates each available provider
      └─ Adds to manager in priority order
   └─ Logs provider status

3. image_adapter uses the manager
   └─ Manager tries providers in order
   └─ Falls back automatically on failure
```

### Important Trade-off

Provider health state (rate-limit backoffs, consecutive-error counts) no longer persists across videos. This is intentional to ensure:
- **Isolation**: No cross-contamination between video generations**
- **Predictability**: Each video starts with a clean slate

The trade-off is that if a provider fails for video A, video B will try again immediately, even if the failure was recent (e.g., a 429 from Pollinations). This is considered acceptable for most use cases.


## Adding a New Provider

### Step 1: Implement Provider Class
Create `src/image_providers/newprovider.py`:
```python
from src.image_providers.base import ImageProvider, ProviderResult

class NewProvider(ImageProvider):
    def __init__(self, api_key: str):
        super().__init__("newprovider")
        self.api_key = api_key
    
    def generate(self, prompt: str, **kwargs) -> ProviderResult:
        # Implementation
        pass
```

### Step 2: Register in Registry
Update `src/image_providers/registry.py`:
```python
def _register_default_providers(self):
    # ... existing registrations ...
    
    # Add new provider
    self.register(ProviderSpec(
        name="New Provider",
        provider_id="newprovider",
        provider_class=NewProvider,
        credential_env_vars={"api_key": "NEWPROVIDER_API_KEY"},
        priority=35  # Between Pollinations and HF FLUX
    ))
```

### Step 3: Add Environment Variable
Update `.env`:
```bash
NEWPROVIDER_API_KEY=your-api-key
```

That's it! The provider will automatically be registered and tried.

## Testing

Run registry tests:
```bash
pytest tests/test_provider_registry.py -v
```

Key test coverage:
- ✅ Provider spec initialization and credential checking
- ✅ Registry initialization with built-in providers
- ✅ Provider registration and deduplication
- ✅ Available provider filtering and sorting
- ✅ Auto-registration with and without credentials
- ✅ Priority ordering
- ✅ Integration with image adapter

## Migration from Old System

**Before (hardcoded):**
```python
# image_adapter.py
_provider_manager.add_cloudflare(...)
_provider_manager.add_siliconflow(...)
_provider_manager.add_pollinations()
# ... repeat for each provider
```

**After (declarative):**
```python
# image_adapter.py
from src.image_providers.registry import auto_register_providers
auto_register_providers(_provider_manager)
```

The old `add_*()` methods still exist for backward compatibility, but new code should use the registry system.

## Benefits Summary

| Aspect | Old System | New System |
|--------|-----------|-----------|
| Adding provider | Edit adapter code | Update registry only |
| Provider priorities | Implicit in code order | Explicit in specs |
| Credential checking | Scattered logic | Centralized |
| Visibility | Hidden in code | Clear logging |
| Testability | Hard to mock | Easy to mock |
| Scalability | O(n) hardcoded calls | O(1) auto-register call |

## Future Enhancements

1. **Config File Support**: Load provider specs from YAML/JSON
2. **Provider Weights**: Learn optimal provider ordering from success metrics
3. **Dynamic Registration**: Add/remove providers at runtime
4. **Provider Health**: Track provider health and adjust ordering
5. **Cost Tracking**: Integrate with cost tracking (pricing per provider)

## References

- Design Pattern: Registry Pattern
- Python Dataclasses: [PEP 557](https://www.python.org/dev/peps/pep-0557/)
- Related Architectural Decision: [TANDA_6_REVIEW.md](TANDA_6_REVIEW.md) — Image Provider Refactor
