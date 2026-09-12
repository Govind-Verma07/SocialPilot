"""
app/services/social_providers/youtube.py
----------------------------------------
YouTube (Google OAuth 2.0) Provider.
"""

from typing import Any, Dict
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider


class YouTubeProvider(BaseSocialProvider):
    platform = SocialPlatform.youtube
    display_name = "YouTube"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    PROFILE_URL = "https://www.googleapis.com/youtube/v3/channels"

    def is_configured(self) -> bool:
        return bool(settings.YOUTUBE_CLIENT_ID and settings.YOUTUBE_CLIENT_SECRET)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/youtube.upload",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        data = {
            "code": code,
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token"),
                "expires_in": res_data.get("expires_in", 3600),
                "token_type": res_data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"part": "snippet,statistics", "mine": "true"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, headers=headers, params=params)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            item = items[0] if items else {}
            snippet = item.get("snippet", {})
            title = snippet.get("title", "YouTube Channel")
            thumbnails = snippet.get("thumbnails", {})
            pic_url = thumbnails.get("default", {}).get("url")

            return {
                "platform_account_id": str(item.get("id", "youtube_channel")),
                "account_name": title,
                "account_username": snippet.get("customUrl", title.lower().replace(" ", "_")),
                "profile_picture_url": pic_url,
                "raw_metadata": item,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        data = {
            "client_id": settings.YOUTUBE_CLIENT_ID,
            "client_secret": settings.YOUTUBE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            resp.raise_for_status()
            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token", refresh_token),
                "expires_in": res_data.get("expires_in", 3600),
            }
