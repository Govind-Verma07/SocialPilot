"""
app/services/social_providers/linkedin.py
-----------------------------------------
LinkedIn OAuth 2.0 Provider.
"""

from typing import Any, Dict
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider


class LinkedInProvider(BaseSocialProvider):
    platform = SocialPlatform.linkedin
    display_name = "LinkedIn"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    PROFILE_URL = "https://api.linkedin.com/v2/userinfo"

    def is_configured(self) -> bool:
        return bool(settings.LINKEDIN_CLIENT_ID and settings.LINKEDIN_CLIENT_SECRET)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "openid profile email w_member_social",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, headers=headers)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token"),
                "expires_in": res_data.get("expires_in", 5184000),
                "token_type": "Bearer",
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            name = data.get("name", "LinkedIn Member")
            return {
                "platform_account_id": str(data.get("sub", data.get("id"))),
                "account_name": name,
                "account_username": name.lower().replace(" ", "_"),
                "profile_picture_url": data.get("picture"),
                "raw_metadata": data,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token", refresh_token),
                "expires_in": res_data.get("expires_in", 5184000),
            }
