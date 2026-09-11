"""
app/services/social_providers/__init__.py
-----------------------------------------
Registry and factory for social media platform providers.
"""

from typing import Dict, List, Optional
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider
from app.services.social_providers.facebook import FacebookProvider
from app.services.social_providers.instagram import InstagramProvider
from app.services.social_providers.linkedin import LinkedInProvider
from app.services.social_providers.x import XProvider
from app.services.social_providers.youtube import YouTubeProvider
from app.services.social_providers.pinterest import PinterestProvider

_PROVIDERS: Dict[SocialPlatform, BaseSocialProvider] = {
    SocialPlatform.facebook:  FacebookProvider(),
    SocialPlatform.instagram: InstagramProvider(),
    SocialPlatform.linkedin:  LinkedInProvider(),
    SocialPlatform.x:         XProvider(),
    SocialPlatform.youtube:   YouTubeProvider(),
    SocialPlatform.pinterest: PinterestProvider(),
}


def get_provider(platform: SocialPlatform | str) -> Optional[BaseSocialProvider]:
    """Retrieve the provider instance for a platform enum or string key."""
    if isinstance(platform, str):
        try:
            platform = SocialPlatform(platform.lower())
        except ValueError:
            return None
    return _PROVIDERS.get(platform)


def get_all_providers() -> Dict[SocialPlatform, BaseSocialProvider]:
    """Return all registered platform providers."""
    return _PROVIDERS
