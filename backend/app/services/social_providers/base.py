"""
app/services/social_providers/base.py
-------------------------------------
Abstract base class for Social Media OAuth Providers.
Each platform implements its own authorization URL building, code exchange,
profile retrieval, and token refreshing logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.models.enums import SocialPlatform


class BaseSocialProvider(ABC):
    platform: SocialPlatform
    display_name: str
    supported_permissions: List[str] = [
        "profile_read",
        "content_publish",
        "analytics_read",
    ]

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if OAuth Client ID and Secret are configured in environment."""
        pass

    @abstractmethod
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate the platform's OAuth 2.0 / authorization redirect URL."""
        pass

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        Returns:
            {
                "access_token": "...",
                "refresh_token": "...",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
        """
        pass

    @abstractmethod
    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        """
        Fetch authenticated profile details using access token.
        Returns:
            {
                "platform_account_id": "...",
                "account_name": "...",
                "account_username": "...",
                "profile_picture_url": "...",
                "raw_metadata": { ... }
            }
        """
        pass

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token."""
        pass
