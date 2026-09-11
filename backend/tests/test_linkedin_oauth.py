"""
tests/test_linkedin_oauth.py
----------------------------
Comprehensive end-to-end test suite for LinkedIn OAuth 2.0 Authorization Code Flow:
- Provider configuration detection
- Authorization URL generation with required scopes (openid, profile, email, w_member_social)
- Authorization code -> access token exchange
- Profile information retrieval from OpenID Connect userinfo
- Token refresh
- Full OAuth callback integration with Fernet encryption, PostgreSQL persistence,
  user validation, and MongoDB metadata storage
- Disconnect account lifecycle
"""

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.core.config import Settings, settings
from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform, AccountStatus
from app.models.social_account import SocialAccount, AccountPermission, AccountSyncLog
from app.services.social_providers import get_provider
from app.services.social_providers.linkedin import LinkedInProvider


def test_linkedin_provider_configured_detection():
    provider = LinkedInProvider()

    with patch.object(settings, "LINKEDIN_CLIENT_ID", ""), \
         patch.object(settings, "LINKEDIN_CLIENT_SECRET", ""):
        assert provider.is_configured() is False

    with patch.object(settings, "LINKEDIN_CLIENT_ID", "li_client_123"), \
         patch.object(settings, "LINKEDIN_CLIENT_SECRET", "li_secret_456"):
        assert provider.is_configured() is True


def test_linkedin_authorization_url_generation():
    provider = LinkedInProvider()
    with patch.object(settings, "LINKEDIN_CLIENT_ID", "li_client_abc"), \
         patch.object(settings, "LINKEDIN_CLIENT_SECRET", "li_secret_xyz"), \
         patch.object(settings, "LINKEDIN_REDIRECT_URI", "https://real-lions-peel.loca.lt/api/v1/social/oauth/linkedin/callback"), \
         patch.object(settings, "LINKEDIN_SCOPES", "openid profile email w_member_social"):

        auth_url = provider.get_authorization_url(
            state="li_test_state_123",
            redirect_uri="http://fallback/callback"
        )
        assert "https://www.linkedin.com/oauth/v2/authorization" in auth_url
        assert "response_type=code" in auth_url
        assert "client_id=li_client_abc" in auth_url
        assert "redirect_uri=https%3A%2F%2Freal-lions-peel.loca.lt%2Fapi%2Fv1%2Fsocial%2Foauth%2Flinkedin%2Fcallback" in auth_url
        assert "state=li_test_state_123" in auth_url
        assert "openid+profile+email+w_member_social" in auth_url or "openid%20profile%20email%20w_member_social" in auth_url


@pytest.mark.asyncio
async def test_linkedin_token_exchange_success():
    provider = LinkedInProvider()
    fake_token_response = {
        "access_token": "AQX_linkedin_access_token_12345",
        "expires_in": 5184000,
        "scope": "openid profile email w_member_social",
        "token_type": "Bearer"
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_token_response

    with patch.object(settings, "LINKEDIN_CLIENT_ID", "li_client_abc"), \
         patch.object(settings, "LINKEDIN_CLIENT_SECRET", "li_secret_xyz"), \
         patch.object(settings, "LINKEDIN_REDIRECT_URI", "https://real-lions-peel.loca.lt/api/v1/social/oauth/linkedin/callback"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        token_data = await provider.exchange_code("mock_code_123", "http://default/callback")
        assert token_data["access_token"] == "AQX_linkedin_access_token_12345"
        assert token_data["expires_in"] == 5184000
        assert token_data["token_type"] == "Bearer"

        # Verify POST payload sent to LinkedIn Token URL
        called_args, called_kwargs = mock_post.call_args
        assert called_args[0] == provider.TOKEN_URL
        assert called_kwargs["data"]["client_id"] == "li_client_abc"
        assert called_kwargs["data"]["client_secret"] == "li_secret_xyz"
        assert called_kwargs["data"]["redirect_uri"] == "https://real-lions-peel.loca.lt/api/v1/social/oauth/linkedin/callback"
        assert called_kwargs["data"]["grant_type"] == "authorization_code"


@pytest.mark.asyncio
async def test_linkedin_fetch_profile_userinfo():
    provider = LinkedInProvider()
    fake_userinfo = {
        "sub": "urn:li:person:xyz789",
        "name": "Sarah Connor",
        "given_name": "Sarah",
        "family_name": "Connor",
        "picture": "https://media.licdn.com/dms/image/profile.jpg",
        "email": "sarah.connor@example.com",
        "email_verified": True,
        "locale": {"country": "US", "language": "en"}
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_userinfo

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        profile = await provider.fetch_profile("AQX_test_access_token")

        assert profile["platform_account_id"] == "urn:li:person:xyz789"
        assert profile["account_name"] == "Sarah Connor"
        assert profile["account_username"] == "sarah.connor"
        assert profile["profile_picture_url"] == "https://media.licdn.com/dms/image/profile.jpg"
        assert profile["raw_metadata"]["email"] == "sarah.connor@example.com"
        assert profile["raw_metadata"]["email_verified"] is True


@pytest.mark.asyncio
async def test_linkedin_refresh_token():
    provider = LinkedInProvider()
    fake_refresh_resp = {
        "access_token": "AQX_refreshed_token_567",
        "refresh_token": "AQX_new_refresh_token_890",
        "expires_in": 5184000,
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_refresh_resp

    with patch.object(settings, "LINKEDIN_CLIENT_ID", "li_client_abc"), \
         patch.object(settings, "LINKEDIN_CLIENT_SECRET", "li_secret_xyz"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        refreshed = await provider.refresh_access_token("AQX_old_refresh_token")

        assert refreshed["access_token"] == "AQX_refreshed_token_567"
        assert refreshed["refresh_token"] == "AQX_new_refresh_token_890"
        assert refreshed["expires_in"] == 5184000


def test_linkedin_oauth_full_callback_flow(client, db_session):
    """
    End-to-End test of the OAuth callback flow for LinkedIn:
    1. Register/authenticate user
    2. Request LinkedIn authorization URL & state token
    3. Invoke callback endpoint
    4. Verify account belongs to the user, tokens are Fernet-encrypted, and permissions/sync log exist.
    """
    # 1. Register test user
    user_payload = {
        "email": "linkedin_creator@example.com",
        "password": "SecurePassword123!",
        "full_name": "LinkedIn Tester",
        "role": "content_creator",
    }
    reg_resp = client.post("/api/v1/auth/register", json=user_payload)
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["user"]["id"]
    jwt_token = reg_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {jwt_token}"}

    # 2. Call GET /api/v1/social/oauth/linkedin/authorize
    with patch.object(settings, "LINKEDIN_CLIENT_ID", "li_client_val"), \
         patch.object(settings, "LINKEDIN_CLIENT_SECRET", "li_secret_val"), \
         patch.object(settings, "LINKEDIN_REDIRECT_URI", "https://real-lions-peel.loca.lt/api/v1/social/oauth/linkedin/callback"), \
         patch.object(settings, "LINKEDIN_SCOPES", "openid profile email w_member_social"):

        auth_url_resp = client.get("/api/v1/social/oauth/linkedin/authorize", headers=auth_headers)
        assert auth_url_resp.status_code == 200
        auth_data = auth_url_resp.json()
        assert auth_data["is_configured"] is True
        assert "authorization_url" in auth_data

        # Extract state parameter from generated authorization URL
        import urllib.parse
        parsed = urllib.parse.urlparse(auth_data["authorization_url"])
        qs = urllib.parse.parse_qs(parsed.query)
        state = qs["state"][0]

        # 3. Simulate LinkedIn redirecting to callback
        mock_provider = LinkedInProvider()
        mock_token_data = {
            "access_token": "AQX_super_secret_linkedin_token",
            "refresh_token": "AQX_refresh_token_optional",
            "expires_in": 5184000,
            "token_type": "Bearer",
        }
        mock_profile_data = {
            "platform_account_id": "li_member_9999",
            "account_name": "LinkedIn Tester",
            "account_username": "linkedin_tester",
            "profile_picture_url": "https://media.licdn.com/test_pic.jpg",
            "raw_metadata": {"sub": "li_member_9999", "headline": "Marketing Professional"},
        }

        with patch("app.api.v1.endpoints.social.get_provider", return_value=mock_provider), \
             patch.object(mock_provider, "exchange_code", new_callable=AsyncMock) as mock_exchange, \
             patch.object(mock_provider, "fetch_profile", new_callable=AsyncMock) as mock_profile, \
             patch("app.api.v1.endpoints.social.save_social_metadata", new_callable=AsyncMock) as mock_save_meta:

            mock_exchange.return_value = mock_token_data
            mock_profile.return_value = mock_profile_data
            mock_save_meta.return_value = True

            # Trigger callback
            callback_resp = client.get(
                f"/api/v1/social/oauth/linkedin/callback?code=AQX_oauth_code_abc123&state={state}",
                follow_redirects=False,
            )

            # Assert redirect to frontend
            assert callback_resp.status_code in (302, 307)
            loc = callback_resp.headers["location"]
            assert "/accounts?connected=linkedin&status=success" in loc

            # 4. Verify PostgreSQL persistence & security
            account = db_session.query(SocialAccount).filter(
                SocialAccount.platform == "linkedin",
                SocialAccount.platform_account_id == "li_member_9999",
            ).first()

            assert account is not None
            # Verify the account belongs to the currently authenticated SocialPilot user
            assert account.user_id == user_id
            assert account.account_name == "LinkedIn Tester"
            assert account.account_username == "linkedin_tester"
            assert account.status == AccountStatus.connected.value

            # Verify Fernet encryption: plain token must not be in database
            assert account.access_token_encrypted != "AQX_super_secret_linkedin_token"
            decrypted = decrypt_token(account.access_token_encrypted)
            assert decrypted == "AQX_super_secret_linkedin_token"

            # Verify permissions assigned
            perms = db_session.query(AccountPermission).filter(
                AccountPermission.social_account_id == account.id
            ).all()
            perm_names = [p.permission for p in perms]
            assert "profile_read" in perm_names
            assert "content_publish" in perm_names
            assert "analytics_read" in perm_names

            # Verify sync log recorded
            logs = db_session.query(AccountSyncLog).filter(
                AccountSyncLog.social_account_id == account.id
            ).all()
            assert len(logs) >= 1
            assert logs[0].status == "success"

            # Verify MongoDB metadata called
            mock_save_meta.assert_called_once()
            call_kwargs = mock_save_meta.call_args[1]
            assert call_kwargs["social_account_id"] == account.id
            assert call_kwargs["platform"] == "linkedin"
            assert call_kwargs["profile_picture_url"] == "https://media.licdn.com/test_pic.jpg"

            # 5. Test Disconnect
            del_resp = client.delete(f"/api/v1/social/accounts/{account.id}", headers=auth_headers)
            assert del_resp.status_code == 200
            assert "Successfully disconnected" in del_resp.json()["message"]

            # Verify deleted from database
            db_session.expire_all()
            disconn_acc = db_session.query(SocialAccount).filter(SocialAccount.id == account.id).first()
            assert disconn_acc is None
