"""
app/services/social_providers/pinterest.py
------------------------------------------
Pinterest OAuth 2.0 Provider.
"""

from typing import Any, Dict
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider


class PinterestProvider(BaseSocialProvider):
    platform = SocialPlatform.pinterest
    display_name = "Pinterest"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://www.pinterest.com/oauth/"
    TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
    PROFILE_URL = "https://api.pinterest.com/v5/user_account"

    def is_configured(self) -> bool:
        return bool(settings.PINTEREST_CLIENT_ID and settings.PINTEREST_CLIENT_SECRET)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.PINTEREST_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "user_accounts:read,pins:read,pins:write,boards:read,boards:write",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        data = {
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        auth = (settings.PINTEREST_CLIENT_ID, settings.PINTEREST_CLIENT_SECRET)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, auth=auth, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token"),
                "expires_in": res_data.get("expires_in", 2592000),
                "token_type": res_data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            username = data.get("username", "pinterest_user")
            return {
                "platform_account_id": str(data.get("id", username)),
                "account_name": data.get("business_name") or username,
                "account_username": username,
                "profile_picture_url": data.get("profile_image"),
                "raw_metadata": data,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        auth = (settings.PINTEREST_CLIENT_ID, settings.PINTEREST_CLIENT_SECRET)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, auth=auth, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token", refresh_token),
                "expires_in": res_data.get("expires_in", 2592000),
            }
