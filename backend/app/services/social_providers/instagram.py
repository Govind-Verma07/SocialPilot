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

    AUTH_URL = "https://www.instagram.com/oauth/authorize"
    TOKEN_URL = "https://api.instagram.com/oauth/access_token"
    LONG_LIVED_TOKEN_URL = "https://graph.instagram.com/access_token"
    REFRESH_TOKEN_URL = "https://graph.instagram.com/refresh_access_token"
    PROFILE_URL = "https://graph.instagram.com/me"

    def is_configured(self) -> bool:
        return bool(settings.INSTAGRAM_CLIENT_ID and settings.INSTAGRAM_CLIENT_SECRET)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        scopes = getattr(settings, "INSTAGRAM_SCOPES", "") or "instagram_business_basic,instagram_business_content_publish"
        params = {
            "enable_fb_login": "0",
            "force_authentication": "1",
            "client_id": settings.INSTAGRAM_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scopes,
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        clean_code = code.split("#")[0]
        data = {
            "client_id": settings.INSTAGRAM_CLIENT_ID,
            "client_secret": settings.INSTAGRAM_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": clean_code,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, timeout=30.0)
            resp.raise_for_status()
            res_data = resp.json()

            access_token = res_data.get("access_token")
            if not access_token and isinstance(res_data.get("data"), list) and res_data["data"]:
                access_token = res_data["data"][0].get("access_token")

            expires_in = res_data.get("expires_in", 3600)

            # Attempt to exchange short-lived token for long-lived 60-day token
            if access_token and settings.INSTAGRAM_CLIENT_SECRET:
                try:
                    ll_params = {
                        "grant_type": "ig_exchange_token",
                        "client_secret": settings.INSTAGRAM_CLIENT_SECRET,
                        "access_token": access_token,
                    }
                    ll_resp = await client.get(self.LONG_LIVED_TOKEN_URL, params=ll_params, timeout=30.0)
                    if ll_resp.status_code == 200:
                        ll_data = ll_resp.json()
                        access_token = ll_data.get("access_token", access_token)
                        expires_in = ll_data.get("expires_in", 5184000)
                except Exception:
                    pass

            return {
                "access_token": access_token,
                "refresh_token": access_token,
                "expires_in": expires_in,
                "token_type": "Bearer",
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        params = {
            "fields": "id,user_id,username,name,account_type,profile_picture_url",
            "access_token": access_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, params=params, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()

            item = data
            if isinstance(data.get("data"), list) and data["data"]:
                item = data["data"][0]

            ig_id = str(item.get("user_id") or item.get("id") or "")
            username = item.get("username") or item.get("name") or "instagram_user"
            display_name = item.get("name") or f"@{username}"
            pic_url = item.get("profile_picture_url")

            return {
                "platform_account_id": ig_id,
                "account_name": display_name,
                "account_username": username,
                "profile_picture_url": pic_url,
                "raw_metadata": data,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient() as client:
                params = {
                    "grant_type": "ig_refresh_token",
                    "access_token": refresh_token,
                }
                resp = await client.get(self.REFRESH_TOKEN_URL, params=params, timeout=30.0)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "access_token": data.get("access_token", refresh_token),
                        "expires_in": data.get("expires_in", 5184000),
                    }
        except Exception:
            pass
        return {"access_token": refresh_token, "expires_in": 5184000}
