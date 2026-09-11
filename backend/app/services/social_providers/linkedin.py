"""
app/services/social_providers/linkedin.py
-----------------------------------------
LinkedIn OAuth 2.0 Provider.
"""

import logging
from typing import Any, Dict, Tuple
from urllib.parse import urlencode
import httpx

from app.core.config import settings, get_settings
from app.models.enums import SocialPlatform
from app.services.social_providers.base import BaseSocialProvider

logger = logging.getLogger(__name__)


class LinkedInProvider(BaseSocialProvider):
    platform = SocialPlatform.linkedin
    display_name = "LinkedIn"
    supported_permissions = ["profile_read", "content_publish", "analytics_read"]

    AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    PROFILE_URL = "https://api.linkedin.com/v2/userinfo"

    def _get_credentials(self) -> Tuple[str, str]:
        s = get_settings()
        client_id = (s.LINKEDIN_CLIENT_ID or "").strip()
        client_secret = (s.LINKEDIN_CLIENT_SECRET or "").strip()
        return client_id, client_secret

    def is_configured(self) -> bool:
        client_id, client_secret = self._get_credentials()
        return bool(client_id and client_secret)

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        s = get_settings()
        client_id, _ = self._get_credentials()
        effective_redirect_uri = getattr(s, "LINKEDIN_REDIRECT_URI", "") or redirect_uri
        raw_scopes = getattr(s, "LINKEDIN_SCOPES", "") or "openid profile email w_member_social"
        cleaned_scopes = " ".join(raw_scopes.replace(",", " ").split())
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": effective_redirect_uri,
            "state": state,
            "scope": cleaned_scopes,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        s = get_settings()
        client_id, client_secret = self._get_credentials()
        effective_redirect_uri = getattr(s, "LINKEDIN_REDIRECT_URI", "") or redirect_uri
        clean_code = code.split("#")[0].rstrip("_")
        data = {
            "grant_type": "authorization_code",
            "code": clean_code,
            "redirect_uri": effective_redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, headers=headers)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error_description") or err_json.get("error") or resp.text
                except Exception:
                    err_detail = resp.text
                logger.error("LinkedIn token exchange failed: %s", err_detail)
                raise ValueError(f"LinkedIn token exchange failed ({resp.status_code}): {err_detail}")

            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token"),
                "expires_in": res_data.get("expires_in", 5184000),
                "token_type": res_data.get("token_type", "Bearer"),
            }

    async def fetch_profile(self, access_token: str) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.PROFILE_URL, headers=headers)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("message") or err_json.get("error") or resp.text
                except Exception:
                    err_detail = resp.text
                logger.error("LinkedIn profile fetch failed: %s", err_detail)
                raise ValueError(f"LinkedIn profile fetch failed ({resp.status_code}): {err_detail}")

            data = resp.json()
            given_name = data.get("given_name", "")
            family_name = data.get("family_name", "")
            full_name = data.get("name") or f"{given_name} {family_name}".strip() or "LinkedIn Member"
            sub = str(data.get("sub") or data.get("id") or "linkedin_user")
            email = data.get("email", "")
            username = email.split("@")[0] if email else full_name.lower().replace(" ", "_")
            picture = data.get("picture")

            return {
                "platform_account_id": sub,
                "account_name": full_name,
                "account_username": username,
                "profile_picture_url": picture,
                "raw_metadata": {
                    "sub": sub,
                    "name": full_name,
                    "given_name": given_name,
                    "family_name": family_name,
                    "email": email,
                    "picture": picture,
                    "email_verified": data.get("email_verified"),
                    "locale": data.get("locale"),
                    "raw_userinfo": data,
                },
            }

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        client_id, client_secret = self._get_credentials()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data=data, headers=headers)
            if resp.is_error:
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error_description") or err_json.get("error") or resp.text
                except Exception:
                    err_detail = resp.text
                logger.error("LinkedIn token refresh failed: %s", err_detail)
                raise ValueError(f"LinkedIn token refresh failed ({resp.status_code}): {err_detail}")

            res_data = resp.json()
            return {
                "access_token": res_data.get("access_token"),
                "refresh_token": res_data.get("refresh_token", refresh_token),
                "expires_in": res_data.get("expires_in", 5184000),
            }
