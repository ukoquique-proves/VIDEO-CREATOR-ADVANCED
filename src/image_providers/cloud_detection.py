"""
Cloud Infrastructure Detection & IP Geolocation

Detects if running on cloud infrastructure (AWS, DigitalOcean, Hetzner, etc.)
and identifies IP blocks that are known to be banned by certain providers
(e.g., Pollinations bans cloud provider IP ranges).
"""

import logging
from typing import Dict, Set, Optional, Tuple
from enum import Enum
import socket

logger = logging.getLogger(__name__)


class CloudProvider(Enum):
    """Known cloud providers with IP-blocking issues."""
    AWS = "aws"
    DIGITALOCEAN = "digitalocean"
    HETZNER = "hetzner"
    LINODE = "linode"
    VULTR = "vultr"
    SCALEWAY = "scaleway"
    CONTABO = "contabo"
    LOCAL = "local"
    UNKNOWN = "unknown"


class BannedProviders:
    """Defines which providers are known to be banned from which cloud IPs."""
    
    # Maps cloud provider to list of banned image providers.
    # This registry prevents known blocked providers from being attempted
    # on cloud infrastructure where they are expected to fail quickly.
    CLOUD_PROVIDER_BANS: Dict[CloudProvider, list] = {
        CloudProvider.AWS: ["pollinations"],
        CloudProvider.DIGITALOCEAN: ["pollinations"],
        CloudProvider.HETZNER: ["pollinations"],
    }
    
    @classmethod
    def is_banned(cls, cloud: CloudProvider, image_provider: str) -> bool:
        """Check if an image provider is banned on this cloud."""
        if cloud not in cls.CLOUD_PROVIDER_BANS:
            return False
        return image_provider.lower() in cls.CLOUD_PROVIDER_BANS[cloud]


def _get_local_ip() -> Optional[str]:
    """Get the local machine's IP address."""
    try:
        # Connect to a public DNS to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.debug(f"Could not determine local IP: {e}")
        return None


def _is_ip_in_range(ip: str, cidr: str) -> bool:
    """Check if IP is in CIDR range."""
    try:
        import ipaddress
        ip_obj = ipaddress.ip_address(ip)
        network = ipaddress.ip_network(cidr, strict=False)
        return ip_obj in network
    except Exception:
        return False


class CloudDetector:
    """Detects cloud infrastructure and associated IP blocks."""
    
    # AWS IP ranges (subset - common regions)
    AWS_RANGES = [
        "10.0.0.0/8",  # AWS VPC default range
        "172.16.0.0/12",  # AWS internal
    ]
    
    # DigitalOcean metadata server
    DIGITALOCEAN_METADATA_URL = "http://169.254.169.254/metadata/v1/id"
    
    # Hetzner metadata server
    HETZNER_METADATA_URL = "http://169.254.169.254/hetzner/v1/metadata"
    
    # Azure metadata
    AZURE_METADATA_URL = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
    
    # Common cloud provider hostnames (reverse DNS)
    CLOUD_HOSTNAMES = {
        "ec2": CloudProvider.AWS,
        "amazonaws": CloudProvider.AWS,
        "digitalocean": CloudProvider.DIGITALOCEAN,
        "hetzner": CloudProvider.HETZNER,
        "linode": CloudProvider.LINODE,
        "vultr": CloudProvider.VULTR,
        "scaleway": CloudProvider.SCALEWAY,
        "contabo": CloudProvider.CONTABO,
    }
    
    def __init__(self):
        self.detected_cloud: Optional[CloudProvider] = None
        self.ip_address: Optional[str] = None
        self._detect()
    
    def _detect(self):
        """Perform cloud detection."""
        local_ip = _get_local_ip()
        self.ip_address = local_ip
        
        if not local_ip:
            self.detected_cloud = CloudProvider.UNKNOWN
            return
        
        # Check reverse DNS for cloud provider keywords
        try:
            hostname = socket.getfqdn(local_ip)
            hostname_lower = hostname.lower()
            
            for keyword, provider in self.CLOUD_HOSTNAMES.items():
                if keyword in hostname_lower:
                    logger.info(f"Detected cloud provider: {provider.value} (hostname: {hostname})")
                    self.detected_cloud = provider
                    return
        except Exception as e:
            logger.debug(f"Could not perform reverse DNS: {e}")
        
        # Check metadata endpoints (cloud-specific)
        if self._check_metadata_endpoint(self.DIGITALOCEAN_METADATA_URL):
            logger.info("Detected DigitalOcean via metadata endpoint")
            self.detected_cloud = CloudProvider.DIGITALOCEAN
            return
        
        if self._check_metadata_endpoint(self.HETZNER_METADATA_URL):
            logger.info("Detected Hetzner via metadata endpoint")
            self.detected_cloud = CloudProvider.HETZNER
            return
        
        if self._check_metadata_endpoint(self.AZURE_METADATA_URL):
            logger.info("Detected Azure via metadata endpoint")
            self.detected_cloud = CloudProvider.AWS  # Treat as cloud
            return
        
        # Check IP ranges
        for aws_range in self.AWS_RANGES:
            if _is_ip_in_range(local_ip, aws_range):
                logger.info(f"Detected AWS via IP range: {local_ip}")
                self.detected_cloud = CloudProvider.AWS
                return
        
        logger.debug(f"No cloud provider detected. Running locally with IP: {local_ip}")
        self.detected_cloud = CloudProvider.LOCAL
    
    def _check_metadata_endpoint(self, url: str) -> bool:
        """Check if a cloud metadata endpoint is accessible."""
        try:
            import requests
            response = requests.get(
                url,
                timeout=2,
                headers={"Metadata-Flavor": "Google"}  # Compatibility with some metadata services
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def is_cloud(self) -> bool:
        """Check if running on cloud infrastructure."""
        return self.detected_cloud not in (
            CloudProvider.LOCAL,
            CloudProvider.UNKNOWN,
            None
        )
    
    def get_cloud_provider(self) -> CloudProvider:
        """Get detected cloud provider."""
        return self.detected_cloud or CloudProvider.UNKNOWN
    
    def get_banned_providers(self) -> Set[str]:
        """Get list of providers banned on this infrastructure."""
        if not self.is_cloud():
            return set()
        
        cloud = self.get_cloud_provider()
        return set(BannedProviders.CLOUD_PROVIDER_BANS.get(cloud, []))
    
    def is_provider_banned(self, provider_name: str) -> bool:
        """Check if a specific provider is banned on this infrastructure."""
        return provider_name.lower() in self.get_banned_providers()


# Global detector instance
_detector: Optional[CloudDetector] = None


def get_detector() -> CloudDetector:
    """Get or create the global CloudDetector instance."""
    global _detector
    if _detector is None:
        _detector = CloudDetector()
    return _detector


def get_cloud_provider() -> CloudProvider:
    """Get the detected cloud provider."""
    return get_detector().get_cloud_provider()


def is_cloud() -> bool:
    """Check if running on cloud infrastructure."""
    return get_detector().is_cloud()


def is_provider_banned(provider_name: str) -> bool:
    """Check if a provider is banned on this infrastructure."""
    return get_detector().is_provider_banned(provider_name)


def get_recommended_timeout(provider_name: str, default_timeout: int = 60) -> int:
    """
    Get recommended timeout for a provider based on infrastructure.
    
    Cloud-hosted providers that are banned should have shorter timeouts
    to fail fast instead of waiting for connection timeout.
    """
    if is_provider_banned(provider_name):
        # Use shorter timeout (5 seconds) for known-banned providers to fail fast
        return 5
    return default_timeout
