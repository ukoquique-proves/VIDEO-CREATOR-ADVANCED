# Cloud Detection & Request Timeout Optimization

## Overview

This feature addresses execution time wasted on HTTP timeouts when running on blocked cloud infrastructure. When deploying on AWS, DigitalOcean, Hetzner, or other cloud providers, certain image providers (e.g., Pollinations) have IP-based blocks that cause 6-30 second timeout delays per request.

## How It Works

### 1. **Cloud Infrastructure Detection** (`cloud_detection.py`)

The system automatically detects which cloud infrastructure (if any) is running the application:

- **Reverse DNS lookup** on local IP address (e.g., `ec2-*.amazonaws.com` → AWS)
- **Cloud metadata endpoints** (DigitalOcean, Hetzner, Azure metadata servers)
- **IP range checks** (AWS VPC ranges like `10.0.0.0/8`)
- **Hostname pattern matching** against known cloud provider patterns

### 2. **Known Bans Registry**

Maintains a registry of which image providers are known to be IP-banned on which cloud platforms:

```python
CLOUD_PROVIDER_BANS = {
    CloudProvider.AWS: ["pollinations"],
    CloudProvider.DIGITALOCEAN: ["pollinations"],
    CloudProvider.HETZNER: ["pollinations"],
    # ... etc
}
```

### 3. **Reduced Timeout on Banned Providers**

When a provider is detected as banned on the current infrastructure:
- **Default timeout** (for normal providers): 60 seconds
- **Banned provider timeout**: 5 seconds (fail-fast)

This reduces wait time from 30+ seconds per banned provider to 5 seconds.

### 4. **Provider Skipping**

The provider manager:
1. Logs cloud detection at startup: `"Detected cloud provider: aws"`
2. Logs which providers are banned: `"Providers banned on this infrastructure: pollinations"`
3. Skips banned providers automatically without attempting connection
4. Returns clear error message if all providers are banned

## Impact on Performance

### Before Implementation
- Running on AWS with Pollinations as primary provider: ~30 second timeout × N retry attempts
- Total generation time could exceed 1-2 minutes on bad cloud IP ranges

### After Implementation
- Detects AWS at startup (~100ms)
- Marks Pollinations as unavailable immediately (no wait)
- Fallback to next available provider (SiliconFlow, HuggingFace, etc.)
- Total overhead: ~100ms detection + immediate fallover
- **Time saved per generation: 20-60 seconds on cloud providers**

## Configuration

No configuration required—detection happens automatically at provider manager initialization.

However, you can manually control behavior:

```python
from src.image_providers import cloud_detection

# Check current infrastructure
detector = cloud_detection.get_detector()
print(f"Running on: {detector.get_cloud_provider()}")

# Check if specific provider is banned
is_banned = cloud_detection.is_provider_banned("pollinations")

# Get recommended timeout for a provider
timeout = cloud_detection.get_recommended_timeout("pollinations", default_timeout=60)
```

## Code Changes

### New Files
- `src/image_providers/cloud_detection.py` - Cloud detection logic & IP checks
- `tests/test_cloud_detection.py` - 14 unit tests + 1 integration test

### Modified Files
- `src/image_providers/base.py` - Added `is_banned_on_infrastructure` flag
- `src/image_providers/pollinations.py` - Uses recommended timeout, respects banned flag
- `src/image_providers/manager.py` - Detects cloud at init, logs bans, skips banned providers

## Testing

Run cloud detection tests:
```bash
pytest tests/test_cloud_detection.py -v
```

Key test scenarios:
- ✅ Cloud detection identifies infrastructure (AWS/DO/Hetzner)
- ✅ Banned providers registry works correctly
- ✅ Recommended timeouts are applied (5s for banned, 60s for others)
- ✅ Pollinations respects banned flag and returns clear error
- ✅ Provider manager skips banned providers without trying
- ✅ Error messages inform user when providers are IP-blocked

## Logging

When running on cloud infrastructure, you'll see logs like:

```
INFO - Detected cloud provider: aws
INFO - Providers banned on this infrastructure: pollinations
DEBUG - Skipping pollinations (IP-blocked on this cloud infrastructure)
INFO - Trying provider 1/5: siliconflow...
INFO - Success with siliconflow: output/generated/siliconflow_1234.png
```

## Supported Cloud Platforms

Currently detects and knows bans for:
- AWS (EC2)
- DigitalOcean
- Hetzner
- Linode
- Vultr
- Scaleway
- Contabo

Easy to add more—just update the `CLOUD_PROVIDER_BANS` dict and add metadata endpoint checks.

## Future Enhancements

1. **Provider health monitoring**: Track success rates per provider per cloud infrastructure
2. **Dynamic timeout tuning**: Adjust timeouts based on provider response patterns
3. **Provider rotation strategy**: Smarter provider ordering based on cloud-specific performance
4. **User notifications**: Alert users in Streamlit UI if running on cloud with limited provider options

## References

- [IP Range Detection Library](https://docs.python.org/3/library/ipaddress.html)
- Cloud Metadata Endpoints:
  - AWS: `http://169.254.169.254/latest/meta-data/`
  - DigitalOcean: `http://169.254.169.254/metadata/v1/`
  - Hetzner: `http://169.254.169.254/hetzner/v1/metadata`
