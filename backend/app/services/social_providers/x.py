"""
app/services/social_providers/x.py
----------------------------------
X (Twitter) OAuth 2.0 with PKCE Provider (RFC 7636).
Supports PKCE code_verifier/code_challenge generation, authorization URL,
token exchange with Basic Auth, profile retrieval from API v2, and token refresh.
"""

import base64
import hashlib
import logging
import secrets
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
import httpx

from app.core.config import settings, get_settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider

logger = logging.getLogger(__name__)


def generate_code_verifier(length: int = 64) -> str:
    """Generate a high-entropy cryptographically random PKCE code_verifier (RFC 7636)."""
    return secrets.token_urlsafe(length)


def generate_code_challenge(code_verifier: str) -> str:
    """Generate SHA-256 (S256) PKCE code_challenge from code_verifier (RFC 7636)."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


class XProvider(BaseSocialProvider):
    platform = SocialPlatform.x
    display_name = "X (Twitter)"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://x.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    PROFILE_URL = "https://api.twitter.com/2/users/me"

    def _get_credentials(self) -> Tuple[str, str]:
        s = get_settings()
        client_id = (s.X_CLIENT_ID or "").strip()
        client_secret = (s.X_CLIENT_SECRET or "").strip()
        return client_id, client_secret

    def is_configured(self) -> bool:
        client_id, client_secret = self._get_credentials()
        return bool(client_id and client_secret)

    def get_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        code_challenge: Optional[str] = None,
        code_challenge_method: str = "S256",
    ) -> str:
        s = get_settings()
        client_id, _ = self._get_credentials()
        effective_redirect_uri = getattr(s, "X_REDIRECT_URI", "") or redirect_uri
        raw_scopes = getattr(s, "X_SCOPES", "") or "tweet.read tweet.write users.read offline.access"
        cleaned_scopes = " ".join(raw_scopes.replace(",", " ").split())

        challenge = code_challenge or "challenge"
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": effective_redirect_uri,
            "scope": cleaned_scopes,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": code_challenge_method,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        s = get_settings()
        client_id, client_secret = self._get_credentials()
        effective_redirect_uri = getattr(s, "X_REDIRECT_URI", "") or redirect_uri
        clean_code = code.split("#")[0].rstrip("_")

        data = {
            "grant_type": "authorization_code",
            "code": clean_code,
            "redirect_uri": effective_redirect_uri,
            "client_id": client_id,
            "code_verifier": code_verifier or "challenge",
        }
        auth = (client_id, client_secret) if client_secret else None
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, auth=auth, headers=headers)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = (
                        err_json.get("error_description")
                        or err_json.get("error")
                        or err_json.get("detail")
                        or resp.text
                    )
                except Exception:
                    err_detail = resp.text
                logger.error("X token exchange failed: %s", err_detail)
                raise ValueError(f"X token exchange failed ({resp.status_code}): {err_detail}")

            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token"),
                "expires_in": res_data.get("expires_in", 7200),
                "token_type": res_data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"user.fields": "id,name,username,profile_image_url,description,public_metrics,verified"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, headers=headers, params=params)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = (
                        err_json.get("detail")
                        or err_json.get("title")
                        or err_json.get("error")
                        or resp.text
                    )
                except Exception:
                    err_detail = resp.text
                logger.error("X profile fetch failed: %s", err_detail)
                raise ValueError(f"X profile fetch failed ({resp.status_code}): {err_detail}")

            res_json = resp.json()
            data = res_json.get("data", {})
            user_id = str(data.get("id"))
            name = data.get("name", "X User")
            username = data.get("username", "x_user")
            profile_picture = data.get("profile_image_url")
            return {
                "platform_account_id": user_id,
                "account_name": name,
                "account_username": username,
                "profile_picture_url": profile_picture,
                "raw_metadata": data,
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        s = get_settings()
        client_id, client_secret = self._get_credentials()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        auth = (client_id, client_secret) if client_secret else None
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, auth=auth, headers=headers)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = (
                        err_json.get("error_description")
                        or err_json.get("error")
                        or err_json.get("detail")
                        or resp.text
                    )
                except Exception:
                    err_detail = resp.text
                logger.error("X token refresh failed: %s", err_detail)
                raise ValueError(f"X token refresh failed ({resp.status_code}): {err_detail}")

            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token", refresh_token),
                "expires_in": res_data.get("expires_in", 7200),
                "token_type": res_data.get("token_type", "Bearer"),
            }
