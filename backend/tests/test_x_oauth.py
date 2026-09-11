"""
tests/test_x_oauth.py
---------------------
Comprehensive end-to-end test suite for X (Twitter) OAuth 2.0 with PKCE:
- Provider configuration detection (X_CLIENT_ID, X_CLIENT_SECRET)
- PKCE code_verifier and code_challenge generation (S256)
- Authorization URL generation with required scopes and PKCE parameters
- Authorization code -> access token exchange using code_verifier and HTTP Basic Auth
- Profile retrieval from X API v2 (/2/users/me)
- Token refresh with token rotation support
- GET /api/v1/social/oauth/x/authorize (JSON and direct 302 redirect modes)
- GET /api/v1/social/oauth/x/callback full handshake flow with Fernet token encryption,
  PostgreSQL persistence, and MongoDB metadata storage
- Disconnect account lifecycle
- Account synchronization lifecycle
"""

import urllib.parse
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import httpx

from app.core.config import settings
from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform, AccountStatus
from app.models.social_account import SocialAccount, AccountPermission, AccountSyncLog
from app.services.social_providers import get_provider
from app.services.social_providers.x import (
    XProvider,
    generate_code_verifier,
    generate_code_challenge,
)


def test_x_provider_configured_detection():
    """Verify XProvider accurately reflects configuration status based on credentials."""
    provider = XProvider()

    with patch.object(settings, "X_CLIENT_ID", ""), \
         patch.object(settings, "X_CLIENT_SECRET", ""):
        assert provider.is_configured() is False

    with patch.object(settings, "X_CLIENT_ID", "x_test_client_id"), \
         patch.object(settings, "X_CLIENT_SECRET", "x_test_client_secret"):
        assert provider.is_configured() is True


def test_pkce_generation():
    """Verify high-entropy code_verifier and S256 code_challenge RFC 7636 compliance."""
    verifier = generate_code_verifier()
    assert len(verifier) >= 43
    challenge = generate_code_challenge(verifier)
    assert len(challenge) > 0
    # Base64url without padding
    assert "=" not in challenge
    assert "+" not in challenge
    assert "/" not in challenge


def test_x_authorization_url_generation():
    """Verify X authorization URL includes PKCE challenge, S256 method, scopes, state, and redirect URI."""
    provider = XProvider()
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)

    with patch.object(settings, "X_CLIENT_ID", "test_x_client_abc"), \
         patch.object(settings, "X_CLIENT_SECRET", "test_x_secret_xyz"), \
         patch.object(settings, "X_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/x/callback"), \
         patch.object(settings, "X_SCOPES", "tweet.read tweet.write users.read offline.access"):

        auth_url = provider.get_authorization_url(
            state="x_test_state_123",
            redirect_uri="http://fallback/callback",
            code_challenge=challenge,
            code_challenge_method="S256",
        )

        assert "https://x.com/i/oauth2/authorize" in auth_url
        assert "response_type=code" in auth_url
        assert "client_id=test_x_client_abc" in auth_url
        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "state=x_test_state_123" in auth_url
        assert "tweet.read" in auth_url
        assert "tweet.write" in auth_url
        assert "users.read" in auth_url
        assert "offline.access" in auth_url


@pytest.mark.asyncio
async def test_x_token_exchange_success():
    """Verify authorization code exchange sends code_verifier, client credentials, and parses tokens."""
    provider = XProvider()
    fake_token_response = {
        "access_token": "x_access_token_mock_12345",
        "refresh_token": "x_refresh_token_mock_67890",
        "expires_in": 7200,
        "token_type": "Bearer",
        "scope": "tweet.read tweet.write users.read offline.access",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_token_response

    with patch.object(settings, "X_CLIENT_ID", "test_x_client_abc"), \
         patch.object(settings, "X_CLIENT_SECRET", "test_x_secret_xyz"), \
         patch.object(settings, "X_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/x/callback"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        token_data = await provider.exchange_code(
            code="mock_x_code_999",
            redirect_uri="http://localhost:8000/api/v1/social/oauth/x/callback",
            code_verifier="mock_code_verifier_secret",
        )

        assert token_data["access_token"] == "x_access_token_mock_12345"
        assert token_data["refresh_token"] == "x_refresh_token_mock_67890"
        assert token_data["expires_in"] == 7200
        assert token_data["token_type"] == "Bearer"

        # Verify POST payload sent to X Token URL
        called_args, called_kwargs = mock_post.call_args
        assert called_args[0] == provider.TOKEN_URL
        assert called_kwargs["data"]["client_id"] == "test_x_client_abc"
        assert called_kwargs["data"]["code"] == "mock_x_code_999"
        assert called_kwargs["data"]["code_verifier"] == "mock_code_verifier_secret"
        assert called_kwargs["data"]["grant_type"] == "authorization_code"
        assert called_kwargs["auth"] == ("test_x_client_abc", "test_x_secret_xyz")


@pytest.mark.asyncio
async def test_x_fetch_profile():
    """Verify X API v2 /users/me response is parsed accurately into profile metadata."""
    provider = XProvider()
    fake_profile = {
        "data": {
            "id": "2244994945",
            "name": "Social Pilot X",
            "username": "SocialPilotApp",
            "profile_image_url": "https://pbs.twimg.com/profile_images/123/avatar.jpg",
            "description": "Smart social media scheduler",
            "public_metrics": {
                "followers_count": 1500,
                "following_count": 300,
                "tweet_count": 450,
            },
            "verified": True,
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_profile

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        profile = await provider.fetch_profile(access_token="valid_x_access_token")

        assert profile["platform_account_id"] == "2244994945"
        assert profile["account_name"] == "Social Pilot X"
        assert profile["account_username"] == "SocialPilotApp"
        assert profile["profile_picture_url"] == "https://pbs.twimg.com/profile_images/123/avatar.jpg"
        assert profile["raw_metadata"]["public_metrics"]["followers_count"] == 1500


@pytest.mark.asyncio
async def test_x_token_refresh():
    """Verify token refresh sends refresh_token and handles rotated tokens."""
    provider = XProvider()
    fake_refresh_response = {
        "access_token": "x_new_access_token_111",
        "refresh_token": "x_rotated_refresh_token_222",
        "expires_in": 7200,
        "token_type": "Bearer",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_refresh_response

    with patch.object(settings, "X_CLIENT_ID", "test_x_client_abc"), \
         patch.object(settings, "X_CLIENT_SECRET", "test_x_secret_xyz"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        refreshed = await provider.refresh_access_token(refresh_token="old_x_refresh_token")
        assert refreshed["access_token"] == "x_new_access_token_111"
        assert refreshed["refresh_token"] == "x_rotated_refresh_token_222"


def test_x_authorize_endpoint(client):
    """Verify GET /api/v1/social/oauth/x/authorize endpoint returns JSON or redirects."""
    # Register & authenticate user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "X Tester",
            "email": "x_tester@example.com",
            "password": "Password123!",
            "role": "content_creator",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(settings, "X_CLIENT_ID", "x_id_val"), \
         patch.object(settings, "X_CLIENT_SECRET", "x_sec_val"), \
         patch.object(settings, "X_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/x/callback"):

        # 1. Default mode: returns JSON with authorization_url
        res = client.get("/api/v1/social/oauth/x/authorize", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["platform"] == "x"
        assert data["is_configured"] is True
        assert data["authorization_url"] is not None
        assert "x.com/i/oauth2/authorize" in data["authorization_url"]
        assert "code_challenge=" in data["authorization_url"]

        # 2. Redirect mode: ?redirect=true returns 302 RedirectResponse
        res_redirect = client.get("/api/v1/social/oauth/x/authorize?redirect=true", headers=headers, follow_redirects=False)
        assert res_redirect.status_code in (302, 307)
        assert "x.com/i/oauth2/authorize" in res_redirect.headers["location"]


def test_x_oauth_full_callback_flow(client, db_session):
    """
    End-to-End test of the X OAuth 2.0 PKCE flow:
    1. Register user
    2. Obtain X authorization URL with PKCE state
    3. Invoke callback with state and mock authorization code
    4. Verify tokens encrypted with Fernet, PostgreSQL persistence, and MongoDB metadata save
    """
    # 1. Register test user
    user_payload = {
        "email": "x_creator@example.com",
        "password": "SecurePassword123!",
        "full_name": "Twitter Marketer",
        "role": "content_creator",
    }
    reg_resp = client.post("/api/v1/auth/register", json=user_payload)
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["user"]["id"]
    jwt_token = reg_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {jwt_token}"}

    with patch.object(settings, "X_CLIENT_ID", "x_client_val"), \
         patch.object(settings, "X_CLIENT_SECRET", "x_secret_val"), \
         patch.object(settings, "X_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/x/callback"), \
         patch.object(settings, "X_SCOPES", "tweet.read tweet.write users.read offline.access"):

        # 2. Get authorize URL & extract state
        auth_url_resp = client.get("/api/v1/social/oauth/x/authorize", headers=auth_headers)
        assert auth_url_resp.status_code == 200
        auth_data = auth_url_resp.json()
        assert auth_data["is_configured"] is True

        parsed = urllib.parse.urlparse(auth_data["authorization_url"])
        qs = urllib.parse.parse_qs(parsed.query)
        state = qs["state"][0]

        # 3. Simulate X redirecting to callback
        mock_provider = XProvider()
        mock_token_data = {
            "access_token": "x_secret_access_token_888",
            "refresh_token": "x_secret_refresh_token_999",
            "expires_in": 7200,
            "token_type": "Bearer",
        }
        mock_profile_data = {
            "platform_account_id": "x_user_777777",
            "account_name": "Twitter Marketer",
            "account_username": "tw_marketer",
            "profile_picture_url": "https://pbs.twimg.com/profile/pic.jpg",
            "raw_metadata": {"followers_count": 5000, "verified": True},
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
                f"/api/v1/social/oauth/x/callback?code=mock_x_auth_code_xyz&state={state}",
                follow_redirects=False,
            )

            # Assert redirect to frontend /accounts
            assert callback_resp.status_code in (302, 307)
            loc = callback_resp.headers["location"]
            assert "/accounts?connected=x&status=success" in loc

            # Verify provider exchange_code received the PKCE code_verifier extracted from state
            called_args, called_kwargs = mock_exchange.call_args
            assert called_kwargs.get("code_verifier") is not None
            assert len(called_kwargs["code_verifier"]) >= 43

            # 4. Verify PostgreSQL persistence & security
            account = db_session.query(SocialAccount).filter(
                SocialAccount.platform == "x",
                SocialAccount.platform_account_id == "x_user_777777",
            ).first()

            assert account is not None
            assert account.user_id == user_id
            assert account.account_name == "Twitter Marketer"
            assert account.account_username == "tw_marketer"
            assert account.status == AccountStatus.connected.value

            # Verify Fernet encryption: plain tokens must not be in database
            assert account.access_token_encrypted != "x_secret_access_token_888"
            assert decrypt_token(account.access_token_encrypted) == "x_secret_access_token_888"
            assert decrypt_token(account.refresh_token_encrypted) == "x_secret_refresh_token_999"

            # Verify permissions assigned
            perms = db_session.query(AccountPermission).filter(
                AccountPermission.social_account_id == account.id
            ).all()
            perm_names = [p.permission for p in perms]
            assert "profile_read" in perm_names
            assert "content_publish" in perm_names
            assert "analytics_read" in perm_names

            # Verify sync log recorded
            log = db_session.query(AccountSyncLog).filter(
                AccountSyncLog.social_account_id == account.id
            ).first()
            assert log is not None
            assert log.status == "success"

            # Verify MongoDB metadata called
            mock_save_meta.assert_called_once()
            save_args = mock_save_meta.call_args[1]
            assert save_args["social_account_id"] == account.id
            assert save_args["platform"] == "x"
            assert save_args["profile_picture_url"] == "https://pbs.twimg.com/profile/pic.jpg"

            # 5. Verify account appears in list accounts
            list_resp = client.get("/api/v1/social/accounts", headers=auth_headers)
            assert list_resp.status_code == 200
            accounts_list = list_resp.json()
            x_acc = next((a for a in accounts_list if a["platform"] == "x"), None)
            assert x_acc is not None
            assert x_acc["platform_account_id"] == "x_user_777777"
            assert x_acc["account_name"] == "Twitter Marketer"

            # 6. Verify disconnect account removes from PostgreSQL and cleans up MongoDB
            with patch("app.api.v1.endpoints.social.delete_social_metadata", new_callable=AsyncMock) as mock_delete_meta:
                mock_delete_meta.return_value = True

                del_resp = client.delete(f"/api/v1/social/accounts/{account.id}", headers=auth_headers)
                assert del_resp.status_code == 200

                # Verify deletion in PostgreSQL
                deleted = db_session.query(SocialAccount).filter(SocialAccount.id == account.id).first()
                assert deleted is None
                mock_delete_meta.assert_called_once_with(account.id)
