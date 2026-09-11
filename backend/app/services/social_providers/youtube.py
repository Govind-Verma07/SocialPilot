"""
app/services/social_providers/youtube.py
----------------------------------------
YouTube (Google OAuth 2.0) Provider.
"""

import logging
from typing import Any, Dict, Tuple
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider

logger = logging.getLogger(__name__)


class YouTubeProvider(BaseSocialProvider):
    platform = SocialPlatform.youtube
    display_name = "YouTube"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    PROFILE_URL = "https://www.googleapis.com/youtube/v3/channels"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def _get_credentials(self) -> Tuple[str, str]:
        client_id = (settings.YOUTUBE_CLIENT_ID or settings.GOOGLE_CLIENT_ID or "").strip()
        client_secret = (settings.YOUTUBE_CLIENT_SECRET or settings.GOOGLE_CLIENT_SECRET or "").strip()
        return client_id, client_secret

    def is_configured(self) -> bool:
        client_id, client_secret = self._get_credentials()
        return bool(client_id and client_secret)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        client_id, _ = self._get_credentials()
        effective_redirect_uri = getattr(settings, "YOUTUBE_REDIRECT_URI", "") or redirect_uri
        scopes = getattr(settings, "YOUTUBE_SCOPES", "") or "https://www.googleapis.com/auth/youtube"
        params = {
            "client_id": client_id,
            "redirect_uri": effective_redirect_uri,
            "response_type": "code",
            "scope": scopes,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        client_id, client_secret = self._get_credentials()
        effective_redirect_uri = getattr(settings, "YOUTUBE_REDIRECT_URI", "") or redirect_uri
        clean_code = code.split("#")[0].rstrip("_")
        data = {
            "code": clean_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": effective_redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error_description") or err_json.get("error") or resp.text
                except Exception:
                    err_detail = resp.text
                logger.error("YouTube token exchange failed: %s", err_detail)
                raise ValueError(f"YouTube token exchange failed ({resp.status_code}): {err_detail}")

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
            # 1. Attempt to fetch primary YouTube channel
            try:
                resp = await client.get(self.PROFILE_URL, headers=headers, params=params)
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    if items:
                        item = items[0]
                        snippet = item.get("snippet", {})
                        title = snippet.get("title", "YouTube Channel")
                        thumbnails = snippet.get("thumbnails", {})
                        pic_url = (
                            thumbnails.get("high", {}).get("url")
                            or thumbnails.get("medium", {}).get("url")
                            or thumbnails.get("default", {}).get("url")
                        )
                        channel_id = str(item.get("id"))
                        custom_url = snippet.get("customUrl") or title.lower().replace(" ", "_")

                        return {
                            "platform_account_id": channel_id,
                            "account_name": title,
                            "account_username": custom_url.lstrip("@"),
                            "profile_picture_url": pic_url,
                            "raw_metadata": {
                                "type": "channel",
                                "channel": item,
                            },
                        }
            except Exception as exc:
                logger.warning("YouTube channel lookup failed, falling back to Google userinfo: %s", exc)

            # 2. Fallback to Google User Profile if user has not yet created a YouTube channel
            try:
                userinfo_resp = await client.get(self.USERINFO_URL, headers=headers)
                if userinfo_resp.status_code == 200:
                    user_data = userinfo_resp.json()
                    sub = str(user_data.get("sub", "google_user"))
                    name = user_data.get("name", "YouTube Creator")
                    email = user_data.get("email", "")
                    pic = user_data.get("picture")
                    username = email.split("@")[0] if email else name.lower().replace(" ", "_")
                    return {
                        "platform_account_id": sub,
                        "account_name": f"{name} (YouTube)",
                        "account_username": username,
                        "profile_picture_url": pic,
                        "raw_metadata": {
                            "type": "google_account",
                            "user": user_data,
                        },
                    }
            except Exception as exc:
                logger.error("Google userinfo fallback failed: %s", exc)

            return {
                "platform_account_id": "youtube_account",
                "account_name": "YouTube Channel",
                "account_username": "youtube_channel",
                "profile_picture_url": None,
                "raw_metadata": {},
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        client_id, client_secret = self._get_credentials()
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error_description") or err_json.get("error") or resp.text
                except Exception:
                    err_detail = resp.text
                logger.error("YouTube token refresh failed: %s", err_detail)
                raise ValueError(f"YouTube token refresh failed ({resp.status_code}): {err_detail}")

            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token", refresh_token),
                "expires_in": res_data.get("expires_in", 3600),
            }
