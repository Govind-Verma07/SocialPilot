"""
tests/test_instagram_oauth.py
------------------------------
Comprehensive test suite for Instagram API with Instagram Login:
- Config synchronization (CLIENT_ID / APP_ID aliases)
- Provider URL generation and scopes
- Short-to-long-lived token exchange
- Profile retrieval with field fallback
- Token refresh
- Full OAuth callback integration with Fernet encryption, PostgreSQL storage,
  and MongoDB metadata persistence.
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
from app.services.social_providers.instagram import InstagramProvider


def test_instagram_provider_configured_detection():
    provider = InstagramProvider()
    
    with patch.object(settings, "INSTAGRAM_CLIENT_ID", ""), \
         patch.object(settings, "INSTAGRAM_CLIENT_SECRET", ""), \
         patch.object(settings, "INSTAGRAM_APP_ID", ""), \
         patch.object(settings, "INSTAGRAM_APP_SECRET", ""):
        assert provider.is_configured() is False

    with patch.object(settings, "INSTAGRAM_CLIENT_ID", "ig_client_123"), \
         patch.object(settings, "INSTAGRAM_CLIENT_SECRET", "ig_secret_456"):
        assert provider.is_configured() is True


def test_instagram_settings_app_id_sync():
    """Verify Settings model_validator maps APP_ID/SECRET to CLIENT_ID/SECRET."""
    s = Settings(
        INSTAGRAM_APP_ID="my_ig_app_id",
        INSTAGRAM_APP_SECRET="my_ig_app_secret",
        INSTAGRAM_CLIENT_ID="",
        INSTAGRAM_CLIENT_SECRET="",
    )
    assert s.INSTAGRAM_CLIENT_ID == "my_ig_app_id"
    assert s.INSTAGRAM_CLIENT_SECRET == "my_ig_app_secret"


def test_instagram_authorization_url_generation():
    provider = InstagramProvider()
    with patch.object(settings, "INSTAGRAM_CLIENT_ID", "1234567890"), \
         patch.object(settings, "INSTAGRAM_CLIENT_SECRET", "secret_abc"), \
         patch.object(settings, "INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/instagram/callback"), \
         patch.object(settings, "INSTAGRAM_SCOPES", "instagram_business_basic"):
        
        url = provider.get_authorization_url(state="secure_state_xyz", redirect_uri="fallback_uri")
        assert "https://api.instagram.com/oauth/authorize" in url
        assert "client_id=1234567890" in url
        assert "response_type=code" in url
        assert "scope=instagram_business_basic" in url
        assert "state=secure_state_xyz" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fsocial%2Foauth%2Finstagram%2Fcallback" in url


@pytest.mark.asyncio
async def test_instagram_token_exchange_success():
    """Test short-lived token exchange followed by long-lived token exchange."""
    provider = InstagramProvider()

    short_lived_response = {
        "access_token": "IG_SHORT_LIVED_TOKEN",
        "user_id": 17841400000000,
        "token_type": "Bearer",
    }
    long_lived_response = {
        "access_token": "IG_LONG_LIVED_TOKEN_60_DAYS",
        "token_type": "Bearer",
        "expires_in": 5184000,
    }

    with patch.object(settings, "INSTAGRAM_CLIENT_ID", "1234567890"), \
         patch.object(settings, "INSTAGRAM_CLIENT_SECRET", "secret_abc"):
        
        async def mock_post(url, data=None):
            req = httpx.Request("POST", url)
            assert data["code"] == "test_auth_code"
            return httpx.Response(200, json=short_lived_response, request=req)

        async def mock_get(url, params=None):
            req = httpx.Request("GET", url)
            assert params["grant_type"] == "ig_exchange_token"
            assert params["access_token"] == "IG_SHORT_LIVED_TOKEN"
            return httpx.Response(200, json=long_lived_response, request=req)

        with patch("httpx.AsyncClient.post", side_effect=mock_post), \
             patch("httpx.AsyncClient.get", side_effect=mock_get):
            
            # Note code has trailing '#_' as Instagram often appends
            tokens = await provider.exchange_code("test_auth_code#_", "http://localhost:8000/callback")
            assert tokens["access_token"] == "IG_LONG_LIVED_TOKEN_60_DAYS"
            assert tokens["expires_in"] == 5184000
            assert tokens["refresh_token"] is None


@pytest.mark.asyncio
async def test_instagram_token_exchange_short_lived_fallback():
    """If long-lived exchange returns non-200, fallback gracefully to short-lived token."""
    provider = InstagramProvider()
    short_lived_response = {
        "access_token": "IG_SHORT_LIVED_TOKEN",
        "user_id": 17841400000000,
    }

    with patch.object(settings, "INSTAGRAM_CLIENT_ID", "1234567890"), \
         patch.object(settings, "INSTAGRAM_CLIENT_SECRET", "secret_abc"):

        async def mock_post(url, data=None):
            return httpx.Response(200, json=short_lived_response, request=httpx.Request("POST", url))

        async def mock_get(url, params=None):
            return httpx.Response(400, text="Cannot exchange", request=httpx.Request("GET", url))

        with patch("httpx.AsyncClient.post", side_effect=mock_post), \
             patch("httpx.AsyncClient.get", side_effect=mock_get):
            
            tokens = await provider.exchange_code("test_code", "http://localhost:8000/callback")
            assert tokens["access_token"] == "IG_SHORT_LIVED_TOKEN"


@pytest.mark.asyncio
async def test_instagram_fetch_profile_full():
    provider = InstagramProvider()
    profile_payload = {
        "id": "178414000000001",
        "username": "creator_pro",
        "name": "Creator Professional",
        "account_type": "BUSINESS",
        "profile_picture_url": "https://scontent.cdninstagram.com/pic.jpg",
        "followers_count": 12500,
        "media_count": 84,
    }

    async def mock_get(url, params=None):
        return httpx.Response(200, json=profile_payload, request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        data = await provider.fetch_profile("fake_token")
        assert data["platform_account_id"] == "178414000000001"
        assert data["account_name"] == "Creator Professional"
        assert data["account_username"] == "creator_pro"
        assert data["profile_picture_url"] == "https://scontent.cdninstagram.com/pic.jpg"
        assert data["raw_metadata"]["followers_count"] == 12500
        assert data["raw_metadata"]["connected_via"] == "instagram_login"


@pytest.mark.asyncio
async def test_instagram_fetch_profile_fallback():
    """If full fields request fails, fallback fields are queried."""
    provider = InstagramProvider()
    fallback_payload = {
        "id": "178414000000002",
        "username": "basic_user",
        "account_type": "MEDIA_CREATOR",
        "media_count": 12,
    }

    call_count = 0

    async def mock_get(url, params=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Full fields failed
            return httpx.Response(400, json={"error": {"message": "Invalid field followers_count"}}, request=httpx.Request("GET", url))
        return httpx.Response(200, json=fallback_payload, request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        data = await provider.fetch_profile("fake_token")
        assert call_count == 2
        assert data["platform_account_id"] == "178414000000002"
        assert data["account_username"] == "basic_user"
        assert data["account_name"] == "@basic_user"


@pytest.mark.asyncio
async def test_instagram_refresh_token():
    provider = InstagramProvider()
    refresh_payload = {
        "access_token": "IG_NEW_REFRESHED_TOKEN",
        "token_type": "Bearer",
        "expires_in": 5184000,
    }

    async def mock_get(url, params=None):
        return httpx.Response(200, json=refresh_payload, request=httpx.Request("GET", url))

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        res = await provider.refresh_access_token("IG_OLD_TOKEN")
        assert res["access_token"] == "IG_NEW_REFRESHED_TOKEN"
        assert res["expires_in"] == 5184000


def test_instagram_oauth_full_callback_flow(client, db_session):
    """
    Test complete callback flow:
    - User initiates Instagram authorization
    - Instagram redirects back with code & state
    - Token exchanged & profile fetched
    - Token Fernet encrypted in PostgreSQL
    - MongoDB metadata saved
    - Redirect to frontend with ?connected=instagram&status=success
    """
    # 1. Register and login user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Instagram Influencer",
            "email": "influencer@example.com",
            "password": "Password123",
            "role": "content_creator",
        },
    )
    user_token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {user_token}"}

    # 2. Configure credentials
    with patch.object(settings, "INSTAGRAM_CLIENT_ID", "ig_app_id_999"), \
         patch.object(settings, "INSTAGRAM_CLIENT_SECRET", "ig_app_secret_999"), \
         patch.object(settings, "INSTAGRAM_REDIRECT_URI", "http://localhost:8000/api/v1/social/oauth/instagram/callback"):

        auth_res = client.get("/api/v1/social/oauth/instagram/authorize", headers=headers)
        assert auth_res.status_code == 200
        auth_data = auth_res.json()
        assert auth_data["is_configured"] is True
        auth_url = auth_data["authorization_url"]
        
        # Extract state from auth_url
        from urllib.parse import parse_qs, urlparse
        query_params = parse_qs(urlparse(auth_url).query)
        state = query_params["state"][0]

        # 3. Simulate callback
        mock_tokens = {
            "access_token": "TEST_RAW_IG_ACCESS_TOKEN",
            "refresh_token": None,
            "expires_in": 5184000,
            "token_type": "Bearer",
        }
        mock_profile = {
            "platform_account_id": "98765432101",
            "account_name": "Insta Star",
            "account_username": "instastar_official",
            "profile_picture_url": "https://img.instagram.com/pic.jpg",
            "raw_metadata": {
                "id": "98765432101",
                "username": "instastar_official",
                "account_type": "BUSINESS",
                "followers_count": 50000,
            },
        }

        with patch("app.services.social_providers.instagram.InstagramProvider.exchange_code", new_callable=AsyncMock) as mock_ex, \
             patch("app.services.social_providers.instagram.InstagramProvider.fetch_profile", new_callable=AsyncMock) as mock_fp, \
             patch("app.api.v1.endpoints.social.save_social_metadata", new_callable=AsyncMock) as mock_mongo:

            mock_ex.return_value = mock_tokens
            mock_fp.return_value = mock_profile
            mock_mongo.return_value = True

            # Meta often appends #_ to the redirect URL or code
            callback_res = client.get(
                f"/api/v1/social/oauth/instagram/callback?code=mock_ig_code%23_&state={state}",
                follow_redirects=False,
            )

            assert callback_res.status_code in [302, 307]
            redirect_target = callback_res.headers["location"]
            assert "/accounts" in redirect_target
            assert "connected=instagram" in redirect_target
            assert "status=success" in redirect_target

            # Verify PostgreSQL record
            account = db_session.query(SocialAccount).filter(
                SocialAccount.platform == "instagram",
                SocialAccount.platform_account_id == "98765432101",
            ).first()

            assert account is not None
            assert account.account_name == "Insta Star"
            assert account.account_username == "instastar_official"
            assert account.status == AccountStatus.connected.value

            # Verify token is encrypted at rest and decrypts to original raw token
            assert account.access_token_encrypted != "TEST_RAW_IG_ACCESS_TOKEN"
            decrypted = decrypt_token(account.access_token_encrypted)
            assert decrypted == "TEST_RAW_IG_ACCESS_TOKEN"

            # Verify permissions and sync log
            perms = db_session.query(AccountPermission).filter(AccountPermission.social_account_id == account.id).all()
            assert len(perms) >= 1

            sync_log = db_session.query(AccountSyncLog).filter(AccountSyncLog.social_account_id == account.id).first()
            assert sync_log is not None
            assert sync_log.status == "success"

            # Verify MongoDB metadata called with right payload
            mock_mongo.assert_called_once()
            call_kwargs = mock_mongo.call_args.kwargs
            assert call_kwargs["social_account_id"] == account.id
            assert call_kwargs["platform"] == "instagram"
            assert call_kwargs["raw_metadata"]["followers_count"] == 50000


