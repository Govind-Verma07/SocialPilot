"""
app/services/social_providers/instagram.py
------------------------------------------
Instagram Graph API / Basic Display OAuth 2.0 Provider.
"""

from typing import Any, Dict
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider


class InstagramProvider(BaseSocialProvider):
    platform = SocialPlatform.instagram
    display_name = "Instagram"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://api.instagram.com/oauth/authorize"
    TOKEN_URL = "https://api.instagram.com/oauth/access_token"
    PROFILE_URL = "https://graph.instagram.com/me"

    def is_configured(self) -> bool:
        return bool(settings.INSTAGRAM_CLIENT_ID and settings.INSTAGRAM_CLIENT_SECRET)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.INSTAGRAM_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "user_profile,user_media",
            "response_type": "code",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        data = {
            "client_id": settings.INSTAGRAM_CLIENT_ID,
            "client_secret": settings.INSTAGRAM_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": None,
                "expires_in": res_data.get("expires_in", 5184000),
                "token_type": "Bearer",
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        params = {
            "fields": "id,username,account_type,media_count",
            "access_token": access_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            username = data.get("username", "instagram_user")
            return {
                "platform_account_id": str(data.get("id")),
                "account_name": f"@{username}",
                "account_username": username,
                "profile_picture_url": None,
                "raw_metadata": data,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        return {"access_token": refresh_token, "expires_in": 5184000}
