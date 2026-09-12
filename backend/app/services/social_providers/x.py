"""
app/services/social_providers/x.py
----------------------------------
X (Twitter) OAuth 2.0 with PKCE Provider.
"""

from typing import Any, Dict
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider


class XProvider(BaseSocialProvider):
    platform = SocialPlatform.x
    display_name = "X (Twitter)"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    PROFILE_URL = "https://api.twitter.com/2/users/me"

    def is_configured(self) -> bool:
        return bool(settings.X_CLIENT_ID and settings.X_CLIENT_SECRET)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": settings.X_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "tweet.read tweet.write users.read offline.access",
            "state": state,
            "code_challenge": "challenge",
            "code_challenge_method": "plain",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": settings.X_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "code_verifier": "challenge",
        }
        auth = (settings.X_CLIENT_ID, settings.X_CLIENT_SECRET)
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, auth=auth)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token"),
                "expires_in": res_data.get("expires_in", 7200),
                "token_type": res_data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"user.fields": "profile_image_url,description,public_metrics"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "platform_account_id": str(data.get("id")),
                "account_name": data.get("name", "X User"),
                "account_username": data.get("username", "x_user"),
                "profile_picture_url": data.get("profile_image_url"),
                "raw_metadata": data,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "client_id": settings.X_CLIENT_ID,
        }
        auth = (settings.X_CLIENT_ID, settings.X_CLIENT_SECRET)
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, auth=auth)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token", refresh_token),
                "expires_in": res_data.get("expires_in", 7200),
            }
