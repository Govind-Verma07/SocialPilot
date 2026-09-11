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

    def _get_credentials(self) -> tuple[str, str]:
        return settings.FACEBOOK_CLIENT_ID, settings.FACEBOOK_CLIENT_SECRET

    def is_configured(self) -> bool:
        client_id, client_secret = self._get_credentials()
        return bool(client_id and client_secret)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        client_id, _ = self._get_credentials()
        effective_redirect_uri = getattr(settings, "FACEBOOK_REDIRECT_URI", "") or redirect_uri
        params = {
            "client_id": client_id,
            "redirect_uri": effective_redirect_uri,
            "state": state,
            "scope": "pages_show_list,pages_read_engagement,public_profile",
            "response_type": "code",
            "auth_type": "rerequest",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        client_id, client_secret = self._get_credentials()
        effective_redirect_uri = getattr(settings, "FACEBOOK_REDIRECT_URI", "") or redirect_uri
        params = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": effective_redirect_uri,
            "code": code,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.TOKEN_URL, params=params)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", resp.text)
                except Exception:
                    err_detail = resp.text
                raise ValueError(f"Facebook token exchange failed ({resp.status_code}): {err_detail}")

            data = resp.json()
            short_lived_token = data.get("access_token")
            expires_in = data.get("expires_in", 5184000)

            # Exchange short-lived token for long-lived token (60-day validity)
            if short_lived_token:
                exchange_params = {
                    "grant_type": "fb_exchange_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "fb_exchange_token": short_lived_token,
                }
                try:
                    ll_resp = await client.get(self.TOKEN_URL, params=exchange_params)
                    if ll_resp.status_code == 200:
                        ll_data = ll_resp.json()
                        access_token = ll_data.get("access_token", short_lived_token)
                        expires_in = ll_data.get("expires_in", 5184000)
                    else:
                        access_token = short_lived_token
                except Exception:
                    access_token = short_lived_token
            else:
                access_token = short_lived_token

            return {
                "access_token": access_token,
                "refresh_token": None,
                "expires_in": expires_in,
                "token_type": data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        # 1. Fetch user profile from /me without email
        user_params = {
            "fields": "id,name,picture.type(large)",
            "access_token": access_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, params=user_params)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", resp.text)
                except Exception:
                    err_detail = resp.text
                raise ValueError(f"Facebook profile fetch failed ({resp.status_code}): {err_detail}")

            user_data = resp.json()
            user_id = str(user_data.get("id"))
            user_name = user_data.get("name", "Facebook User")
            user_pic = user_data.get("picture", {}).get("data", {}).get("url")

            # 2. Check for managed Facebook Pages
            pages = []
            try:
                pages_resp = await client.get(
                    "https://graph.facebook.com/v19.0/me/accounts",
                    params={
                        "fields": "id,name,access_token,category,picture.type(large)",
                        "access_token": access_token,
                    },
                )
                if pages_resp.status_code == 200:
                    pages_json = pages_resp.json()
                    pages = pages_json.get("data", [])
            except Exception:
                pass

            # If user manages Facebook Pages, bind the primary page with its Page Access Token
            if pages and len(pages) > 0:
                primary_page = pages[0]
                page_id = str(primary_page.get("id"))
                page_name = primary_page.get("name", user_name)
                page_pic = primary_page.get("picture", {}).get("data", {}).get("url") or user_pic
                page_token = primary_page.get("access_token")

                return {
                    "platform_account_id": page_id,
                    "account_name": page_name,
                    "account_username": page_name.lower().replace(" ", "_"),
                    "profile_picture_url": page_pic,
                    "access_token": page_token or access_token,
                    "raw_metadata": {
                        "type": "page",
                        "page": primary_page,
                        "all_pages": pages,
                        "user": user_data,
                    },
                }

            # Fallback to personal profile if no page exists yet
            return {
                "platform_account_id": user_id,
                "account_name": user_name,
                "account_username": user_name.lower().replace(" ", "_"),
                "profile_picture_url": user_pic,
                "access_token": access_token,
                "raw_metadata": {
                    "type": "user",
                    "user": user_data,
                },
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        client_id, client_secret = self._get_credentials()
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "fb_exchange_token": refresh_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.TOKEN_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "access_token": data.get("access_token", refresh_token),
                    "expires_in": data.get("expires_in", 5184000),
                }
        return {"access_token": refresh_token, "expires_in": 5184000}
