"""
app/services/social_providers/instagram.py
------------------------------------------
Instagram API with Instagram Login OAuth 2.0 Provider.
Supports authorization, short-to-long-lived token exchange,
profile retrieval, and token refresh.
"""

import logging
from typing import Any, Dict, Tuple
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider

logger = logging.getLogger(__name__)


class InstagramProvider(BaseSocialProvider):
    platform = SocialPlatform.instagram
    display_name = "Instagram"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://api.instagram.com/oauth/authorize"
    TOKEN_URL = "https://api.instagram.com/oauth/access_token"
    GRAPH_TOKEN_URL = "https://graph.instagram.com/access_token"
    REFRESH_TOKEN_URL = "https://graph.instagram.com/refresh_access_token"
    PROFILE_URL = "https://graph.instagram.com/me"

    def _get_credentials(self) -> Tuple[str, str]:
        client_id = (settings.INSTAGRAM_CLIENT_ID or getattr(settings, "INSTAGRAM_APP_ID", "") or "").strip()
        client_secret = (settings.INSTAGRAM_CLIENT_SECRET or getattr(settings, "INSTAGRAM_APP_SECRET", "") or "").strip()
        return client_id, client_secret

    def is_configured(self) -> bool:
        client_id, client_secret = self._get_credentials()
        return bool(client_id and client_secret)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        client_id, _ = self._get_credentials()
        effective_redirect_uri = getattr(settings, "INSTAGRAM_REDIRECT_URI", "") or redirect_uri
        raw_scopes = getattr(settings, "INSTAGRAM_SCOPES", "") or "instagram_business_basic,instagram_business_content_publish"
        cleaned_scopes = ",".join(s.strip() for s in raw_scopes.split(",") if s.strip())
        params = {
            "client_id": client_id,
            "redirect_uri": effective_redirect_uri,
            "scope": cleaned_scopes,
            "response_type": "code",
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        client_id, client_secret = self._get_credentials()
        effective_redirect_uri = getattr(settings, "INSTAGRAM_REDIRECT_URI", "") or redirect_uri
        clean_code = code.split("#")[0].rstrip("_")

        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": effective_redirect_uri,
            "code": clean_code,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = (
                        err_json.get("error_message")
                        or err_json.get("error", {}).get("message")
                        or resp.text
                    )
                except Exception:
                    err_detail = resp.text
                logger.error("Instagram token exchange failed with status %s", resp.status_code)
                raise ValueError(f"Instagram token exchange failed ({resp.status_code}): {err_detail}")

            res_data = resp.json()
            short_lived_token = res_data.get("access_token")
            expires_in = res_data.get("expires_in", 5184000)

            # Exchange short-lived token for long-lived 60-day token
            if short_lived_token:
                ll_params = {
                    "grant_type": "ig_exchange_token",
                    "client_secret": client_secret,
                    "access_token": short_lived_token,
                }
                try:
                    ll_resp = await client.get(self.GRAPH_TOKEN_URL, params=ll_params)
                    if ll_resp.status_code == 200:
                        ll_data = ll_resp.json()
                        access_token = ll_data.get("access_token", short_lived_token)
                        expires_in = ll_data.get("expires_in", 5184000)
                        logger.info("Successfully acquired long-lived Instagram access token")
                    else:
                        logger.warning(
                            "Long-lived Instagram token exchange returned status %s; falling back to short-lived token",
                            ll_resp.status_code,
                        )
                        access_token = short_lived_token
                except Exception as exc:
                    logger.warning("Failed to exchange for long-lived Instagram token: %s", exc)
                    access_token = short_lived_token
            else:
                access_token = short_lived_token

            return {
                "access_token": access_token,
                "refresh_token": None,
                "expires_in": expires_in,
                "token_type": res_data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        full_fields = "id,username,name,account_type,profile_picture_url,followers_count,media_count"
        fallback_fields = "id,username,account_type,media_count"
        minimal_fields = "id,username"

        async with httpx.AsyncClient() as client:
            # 1. Try full fields request
            resp = await client.get(self.PROFILE_URL, params={"fields": full_fields, "access_token": access_token})
            if resp.is_error:
                logger.warning(
                    "Instagram full profile fetch returned %s. Attempting fallback fields.",
                    resp.status_code,
                )
                resp = await client.get(
                    self.PROFILE_URL, params={"fields": fallback_fields, "access_token": access_token}
                )

            if resp.is_error:
                logger.warning(
                    "Instagram fallback profile fetch returned %s. Attempting minimal fields.",
                    resp.status_code,
                )
                resp = await client.get(
                    self.PROFILE_URL, params={"fields": minimal_fields, "access_token": access_token}
                )

            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = (
                        err_json.get("error", {}).get("message")
                        or err_json.get("error_message")
                        or resp.text
                    )
                except Exception:
                    err_detail = resp.text
                logger.error("Instagram profile fetch failed with status %s", resp.status_code)
                raise ValueError(f"Instagram profile fetch failed ({resp.status_code}): {err_detail}")

            data = resp.json()
            user_id = str(data.get("id"))
            username = data.get("username") or "instagram_user"
            name = data.get("name") or username
            pic_url = data.get("profile_picture_url")
            account_type = data.get("account_type")
            media_count = data.get("media_count")
            followers_count = data.get("followers_count")

            return {
                "platform_account_id": user_id,
                "account_name": name if name != username else f"@{username}",
                "account_username": username,
                "profile_picture_url": pic_url,
                "raw_metadata": {
                    "id": user_id,
                    "username": username,
                    "name": name,
                    "account_type": account_type,
                    "media_count": media_count,
                    "followers_count": followers_count,
                    "profile_picture_url": pic_url,
                    "connected_via": "instagram_login",
                },
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh a long-lived Instagram user access token before expiration.
        """
        params = {
            "grant_type": "ig_refresh_token",
            "access_token": refresh_token,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.REFRESH_TOKEN_URL, params=params)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = (
                        err_json.get("error", {}).get("message")
                        or err_json.get("error_message")
                        or resp.text
                    )
                except Exception:
                    err_detail = resp.text
                logger.error("Instagram token refresh failed with status %s", resp.status_code)
                raise ValueError(f"Instagram token refresh failed ({resp.status_code}): {err_detail}")

            data = resp.json()
            return {
                "access_token": data.get("access_token", refresh_token),
                "expires_in": data.get("expires_in", 5184000),
                "token_type": data.get("token_type", "Bearer"),
            }
