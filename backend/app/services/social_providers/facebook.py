"""
app/services/social_providers/facebook.py
-----------------------------------------
Facebook Graph API OAuth 2.0 Provider.
"""

from typing import Any, Dict
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider


class FacebookProvider(BaseSocialProvider):
    platform = SocialPlatform.facebook
    display_name = "Facebook"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
    PROFILE_URL = "https://graph.facebook.com/v19.0/me"

    def is_configured(self) -> bool:
        return bool(settings.FACEBOOK_CLIENT_ID and settings.FACEBOOK_CLIENT_SECRET)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "pages_show_list,pages_read_engagement,pages_manage_posts,public_profile",
            "response_type": "code",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        params = {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "client_secret": settings.FACEBOOK_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.TOKEN_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            return {
                "access_token": data.get("access_token"),
                "refresh_token": None,
                "expires_in": data.get("expires_in", 5184000),
                "token_type": data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        params = {
            "fields": "id,name,picture.type(large)",
            "access_token": access_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            pic_url = data.get("picture", {}).get("data", {}).get("url")
            return {
                "platform_account_id": str(data.get("id")),
                "account_name": data.get("name", "Facebook User"),
                "account_username": data.get("name", "").lower().replace(" ", "_"),
                "profile_picture_url": pic_url,
                "raw_metadata": data,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        return {"access_token": refresh_token, "expires_in": 5184000}
