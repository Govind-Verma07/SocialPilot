"""
tests/test_youtube_oauth.py
----------------------------
Comprehensive end-to-end test suite for YouTube (Google OAuth 2.0):
- Provider configuration detection (YOUTUBE_CLIENT_ID / GOOGLE_CLIENT_ID fallback)
- Authorization URL generation with required scopes, offline access, and consent prompt
- Authorization code -> access & refresh token exchange
- Profile retrieval from YouTube Data API v3 (/youtube/v3/channels?mine=true)
- Fallback to Google User Profile (/oauth2/v3/userinfo) when channel is not yet created
- Token refresh support
- GET /api/v1/social/oauth/youtube/authorize (JSON and direct 302 redirect modes)
- GET /api/v1/social/oauth/youtube/callback full handshake flow with Fernet token encryption,
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
from app.services.social_providers.youtube import YouTubeProvider


def test_youtube_provider_configured_detection():
    """Verify YouTubeProvider accurately detects credentials directly and from Google fallback."""
    provider = YouTubeProvider()

    with patch.object(settings, "YOUTUBE_CLIENT_ID", ""), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", ""), \
         patch.object(settings, "GOOGLE_CLIENT_ID", ""), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", ""):
        assert provider.is_configured() is False

    # Fallback to Google credentials
    with patch.object(settings, "YOUTUBE_CLIENT_ID", ""), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", ""), \
         patch.object(settings, "GOOGLE_CLIENT_ID", "google_client_id_val"), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", "google_client_secret_val"):
        assert provider.is_configured() is True

    # Direct YouTube credentials
    with patch.object(settings, "YOUTUBE_CLIENT_ID", "yt_client_id_val"), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", "yt_client_secret_val"), \
         patch.object(settings, "GOOGLE_CLIENT_ID", ""), \
         patch.object(settings, "GOOGLE_CLIENT_SECRET", ""):
        assert provider.is_configured() is True


def test_youtube_authorization_url_generation():
    """Verify YouTube authorization URL includes offline access, prompt=consent, scopes, state, and redirect URI."""
    provider = YouTubeProvider()

    with patch.object(settings, "YOUTUBE_CLIENT_ID", "test_yt_client_123"), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", "test_yt_secret_456"), \
         patch.object(settings, "YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/youtube/callback"), \
         patch.object(settings, "YOUTUBE_SCOPES", "https://www.googleapis.com/auth/youtube"):

        auth_url = provider.get_authorization_url(
            state="yt_test_state_123",
            redirect_uri="http://fallback/callback",
        )

        assert "https://accounts.google.com/o/oauth2/v2/auth" in auth_url
        assert "response_type=code" in auth_url
        assert "client_id=test_yt_client_123" in auth_url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fsocial%2Foauth%2Fyoutube%2Fcallback" in auth_url or "redirect_uri=http://localhost:8000/api/v1/social/oauth/youtube/callback" in auth_url
        assert "state=yt_test_state_123" in auth_url
        assert "access_type=offline" in auth_url
        assert "prompt=consent" in auth_url
        assert "scope=" in auth_url
        assert urllib.parse.quote("https://www.googleapis.com/auth/youtube", safe="") in auth_url or "https://www.googleapis.com/auth/youtube" in auth_url


@pytest.mark.asyncio
async def test_youtube_token_exchange_success():
    """Verify authorization code exchange sends credentials and parses access and refresh tokens."""
    provider = YouTubeProvider()
    fake_token_response = {
        "access_token": "yt_access_token_mock_12345",
        "refresh_token": "yt_refresh_token_mock_67890",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_token_response

    with patch.object(settings, "YOUTUBE_CLIENT_ID", "test_yt_client_123"), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", "test_yt_secret_456"), \
         patch.object(settings, "YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/youtube/callback"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        token_data = await provider.exchange_code(
            code="mock_yt_auth_code",
            redirect_uri="http://localhost:8000/api/v1/social/oauth/youtube/callback",
        )

        assert token_data["access_token"] == "yt_access_token_mock_12345"
        assert token_data["refresh_token"] == "yt_refresh_token_mock_67890"
        assert token_data["expires_in"] == 3600
        assert token_data["token_type"] == "Bearer"

        called_args, called_kwargs = mock_post.call_args
        assert called_args[0] == provider.TOKEN_URL
        assert called_kwargs["data"]["client_id"] == "test_yt_client_123"
        assert called_kwargs["data"]["client_secret"] == "test_yt_secret_456"
        assert called_kwargs["data"]["code"] == "mock_yt_auth_code"
        assert called_kwargs["data"]["grant_type"] == "authorization_code"


@pytest.mark.asyncio
async def test_youtube_fetch_profile_with_channel():
    """Verify YouTube Data API v3 channel response is parsed accurately into profile metadata."""
    provider = YouTubeProvider()
    fake_channel_response = {
        "items": [
            {
                "id": "UC_x5XG1OV2P6uZZ5FSM9Ttw",
                "snippet": {
                    "title": "Google Developers Tech Channel",
                    "customUrl": "@GoogleDevelopers",
                    "description": "The official YouTube channel for Google developers.",
                    "thumbnails": {
                        "high": {"url": "https://yt3.ggpht.com/high_res_avatar.jpg"},
                    },
                },
                "statistics": {
                    "viewCount": "12345678",
                    "subscriberCount": "2250000",
                    "videoCount": "1500",
                },
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_channel_response

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        profile = await provider.fetch_profile(access_token="valid_yt_access_token")

        assert profile["platform_account_id"] == "UC_x5XG1OV2P6uZZ5FSM9Ttw"
        assert profile["account_name"] == "Google Developers Tech Channel"
        assert profile["account_username"] == "GoogleDevelopers"
        assert profile["profile_picture_url"] == "https://yt3.ggpht.com/high_res_avatar.jpg"
        assert profile["raw_metadata"]["type"] == "channel"
        assert profile["raw_metadata"]["channel"]["statistics"]["subscriberCount"] == "2250000"


@pytest.mark.asyncio
async def test_youtube_fetch_profile_fallback_to_google_userinfo():
    """Verify fallback to Google userinfo when channel list is empty."""
    provider = YouTubeProvider()
    empty_channel_resp = MagicMock()
    empty_channel_resp.status_code = 200
    empty_channel_resp.is_error = False
    empty_channel_resp.json.return_value = {"items": []}

    userinfo_resp = MagicMock()
    userinfo_resp.status_code = 200
    userinfo_resp.is_error = False
    userinfo_resp.json.return_value = {
        "sub": "109876543210987654321",
        "name": "Alex Tech",
        "email": "alex@example.com",
        "picture": "https://lh3.googleusercontent.com/avatar.jpg",
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [empty_channel_resp, userinfo_resp]

        profile = await provider.fetch_profile(access_token="valid_yt_access_token")

        assert profile["platform_account_id"] == "109876543210987654321"
        assert profile["account_name"] == "Alex Tech (YouTube)"
        assert profile["account_username"] == "alex"
        assert profile["profile_picture_url"] == "https://lh3.googleusercontent.com/avatar.jpg"
        assert profile["raw_metadata"]["type"] == "google_account"


@pytest.mark.asyncio
async def test_youtube_token_refresh():
    """Verify YouTube token refresh flow."""
    provider = YouTubeProvider()
    fake_refresh_response = {
        "access_token": "yt_refreshed_access_token_888",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_error = False
    mock_resp.json.return_value = fake_refresh_response

    with patch.object(settings, "YOUTUBE_CLIENT_ID", "test_yt_client_123"), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", "test_yt_secret_456"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        refreshed = await provider.refresh_access_token(refresh_token="old_yt_refresh_token")
        assert refreshed["access_token"] == "yt_refreshed_access_token_888"
        assert refreshed["refresh_token"] == "old_yt_refresh_token"


def test_youtube_authorize_endpoint(client):
    """Verify GET /api/v1/social/oauth/youtube/authorize endpoint returns JSON or redirects."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "YouTube Creator",
            "email": "yt_creator@example.com",
            "password": "Password123!",
            "role": "content_creator",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(settings, "YOUTUBE_CLIENT_ID", "yt_client_val"), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", "yt_secret_val"), \
         patch.object(settings, "YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/youtube/callback"):

        # 1. JSON mode
        res = client.get("/api/v1/social/oauth/youtube/authorize", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["platform"] == "youtube"
        assert data["is_configured"] is True
        assert data["authorization_url"] is not None
        assert "accounts.google.com/o/oauth2/v2/auth" in data["authorization_url"]

        # 2. Redirect mode
        res_redirect = client.get("/api/v1/social/oauth/youtube/authorize?redirect=true", headers=headers, follow_redirects=False)
        assert res_redirect.status_code in (302, 307)
        assert "accounts.google.com/o/oauth2/v2/auth" in res_redirect.headers["location"]


def test_youtube_oauth_full_callback_flow(client, db_session):
    """
    End-to-End test of the YouTube OAuth 2.0 flow:
    1. Register user
    2. Obtain YouTube authorization URL with signed state
    3. Invoke callback with state and mock authorization code
    4. Verify tokens encrypted with Fernet, PostgreSQL persistence, and MongoDB metadata save
    """
    user_payload = {
        "email": "yt_producer@example.com",
        "password": "SecurePassword123!",
        "full_name": "YouTube Producer",
        "role": "content_creator",
    }
    reg_resp = client.post("/api/v1/auth/register", json=user_payload)
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["user"]["id"]
    token = reg_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch.object(settings, "YOUTUBE_CLIENT_ID", "yt_client_e2e"), \
         patch.object(settings, "YOUTUBE_CLIENT_SECRET", "yt_secret_e2e"), \
         patch.object(settings, "YOUTUBE_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/youtube/callback"), \
         patch.object(settings, "FRONTEND_URL", "http://localhost:5173"):

        # 1. Obtain authorization URL and signed state
        auth_resp = client.get("/api/v1/social/oauth/youtube/authorize", headers=headers)
        assert auth_resp.status_code == 200
        auth_url = auth_resp.json()["authorization_url"]
        parsed_url = urllib.parse.urlparse(auth_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        state_token = query_params["state"][0]

        # 2. Mock token exchange & profile responses
        mock_tokens = {
            "access_token": "yt_live_access_token_abc123",
            "refresh_token": "yt_live_refresh_token_def456",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        mock_profile = {
            "items": [
                {
                    "id": "UC_yt_channel_sample_99",
                    "snippet": {
                        "title": "Creative Studio Channel",
                        "customUrl": "@CreativeStudio",
                        "thumbnails": {
                            "high": {"url": "https://yt3.ggpht.com/channel_avatar.jpg"}
                        },
                    },
                    "statistics": {
                        "subscriberCount": "85000",
                        "viewCount": "500000",
                    },
                }
            ]
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
             patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
             patch("app.api.v1.endpoints.social.save_social_metadata", new_callable=AsyncMock) as mock_save_meta:

            mock_post.return_value = MagicMock(status_code=200, is_error=False, json=lambda: mock_tokens)
            mock_get.return_value = MagicMock(status_code=200, is_error=False, json=lambda: mock_profile)
            mock_save_meta.return_value = True

            # 3. Call callback endpoint
            cb_resp = client.get(
                f"/api/v1/social/oauth/youtube/callback?code=mock_google_yt_auth_code&state={state_token}",
                follow_redirects=False,
            )

            assert cb_resp.status_code in (302, 307)
            location = cb_resp.headers["location"]
            assert "accounts?connected=youtube&status=success" in location

            # 4. Verify PostgreSQL persistence
            account = db_session.query(SocialAccount).filter(
                SocialAccount.user_id == user_id,
                SocialAccount.platform == SocialPlatform.youtube.value,
                SocialAccount.platform_account_id == "UC_yt_channel_sample_99",
            ).first()

            assert account is not None
            assert account.account_name == "Creative Studio Channel"
            assert account.account_username == "CreativeStudio"
            assert account.status == AccountStatus.connected.value

            # Verify tokens are encrypted with Fernet
            assert account.access_token_encrypted != "yt_live_access_token_abc123"
            assert decrypt_token(account.access_token_encrypted) == "yt_live_access_token_abc123"
            assert account.refresh_token_encrypted is not None
            assert decrypt_token(account.refresh_token_encrypted) == "yt_live_refresh_token_def456"

            # Verify permissions
            perms = db_session.query(AccountPermission).filter(
                AccountPermission.social_account_id == account.id
            ).all()
            perm_names = [p.permission for p in perms]
            assert "profile_read" in perm_names
            assert "content_publish" in perm_names

            # Verify sync log
            sync_log = db_session.query(AccountSyncLog).filter(
                AccountSyncLog.social_account_id == account.id
            ).first()
            assert sync_log is not None

            # Verify MongoDB metadata call was made
            mock_save_meta.assert_awaited_once()
            called_kwargs = mock_save_meta.call_args.kwargs
            assert called_kwargs["platform"] == "youtube"
            assert called_kwargs["profile_picture_url"] == "https://yt3.ggpht.com/channel_avatar.jpg"
            assert called_kwargs["raw_metadata"]["type"] == "channel"

        # 5. Verify account appears in GET /api/v1/social/accounts
        accs_resp = client.get("/api/v1/social/accounts", headers=headers)
        assert accs_resp.status_code == 200
        accs_data = accs_resp.json()
        yt_accs = [a for a in accs_data if a["platform"] == "youtube"]
        assert len(yt_accs) == 1
        assert yt_accs[0]["account_name"] == "Creative Studio Channel"

        # 6. Verify disconnect account lifecycle
        del_resp = client.delete(f"/api/v1/social/accounts/{account.id}", headers=headers)
        assert del_resp.status_code == 200
        account_after_del = db_session.query(SocialAccount).filter(SocialAccount.id == account.id).first()
        assert account_after_del is None
