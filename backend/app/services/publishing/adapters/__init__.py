"""
app/services/publishing/adapters/__init__.py
-------------------------------------------
Registry of platform publishers.
"""

from typing import Dict, Type

from app.models.enums import SocialPlatform
from app.services.publishing.base import BasePlatformPublisher
from app.services.publishing.adapters.linkedin import LinkedInPublisher
from app.services.publishing.adapters.facebook import FacebookPublisher
from app.services.publishing.adapters.instagram import InstagramPublisher
from app.services.publishing.adapters.x import XPublisher
from app.services.publishing.adapters.youtube import YouTubePublisher
from app.services.publishing.adapters.pinterest import PinterestPublisher

PUBLISHER_REGISTRY: Dict[str, Type[BasePlatformPublisher]] = {
    SocialPlatform.linkedin.value: LinkedInPublisher,
    SocialPlatform.facebook.value: FacebookPublisher,
    SocialPlatform.instagram.value: InstagramPublisher,
    SocialPlatform.x.value: XPublisher,
    SocialPlatform.youtube.value: YouTubePublisher,
    SocialPlatform.pinterest.value: PinterestPublisher,
}


def get_publisher(platform: str) -> BasePlatformPublisher:
    """Instantiate and return the appropriate publisher for a platform."""
    plat_key = platform.lower() if platform else ""
    cls = PUBLISHER_REGISTRY.get(plat_key)
    if not cls:
        raise ValueError(f"Publishing is not supported for platform: {platform}")
    return cls()
