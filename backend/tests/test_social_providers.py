"""
tests/test_social_providers.py
------------------------------
Test suite for Token Encryption at rest, Provider Registry, and Provider Architecture.
"""

import pytest
from app.core.encryption import decrypt_token, encrypt_token
from app.models.enums import SocialPlatform
from app.services.social_metadata_service import get_social_metadata, save_social_metadata
from app.services.social_providers import get_all_providers, get_provider


def test_token_encryption_and_decryption():
    """Test symmetric encryption of OAuth tokens at rest."""
    plain_token = "gho_sample_oauth_secret_access_token_123456789"
    encrypted = encrypt_token(plain_token)

    assert encrypted is not None
    assert encrypted != plain_token
    assert not encrypted.startswith("gho_")

    decrypted = decrypt_token(encrypted)
    assert decrypted == plain_token


def test_token_encryption_none_handling():
    """Test encrypting and decrypting None or empty tokens."""
    assert encrypt_token(None) is None
    assert decrypt_token(None) is None
    assert decrypt_token("invalid_base64_payload") is None


def test_all_six_providers_registered():
    """Verify that all 6 required platforms from PDF exist in registry."""
    providers = get_all_providers()
    expected_platforms = {
        SocialPlatform.facebook,
        SocialPlatform.instagram,
        SocialPlatform.linkedin,
        SocialPlatform.x,
        SocialPlatform.youtube,
        SocialPlatform.pinterest,
    }

    assert set(providers.keys()) == expected_platforms

    for platform in expected_platforms:
        provider = get_provider(platform)
        assert provider is not None
        assert provider.platform == platform
        assert len(provider.supported_permissions) > 0
        assert "profile_read" in provider.supported_permissions


def test_provider_auth_url_generation():
    """Test generating OAuth authorization URLs for providers."""
    x_provider = get_provider("x")
    assert x_provider is not None
    url = x_provider.get_authorization_url(state="test_state_123", redirect_uri="http://localhost:8000/callback")
    assert "https://twitter.com/i/oauth2/authorize" in url
    assert "state=test_state_123" in url
    assert "code_challenge=" in url

    fb_provider = get_provider("facebook")
    fb_url = fb_provider.get_authorization_url(state="fb_state_456", redirect_uri="http://localhost:8000/callback")
    assert "https://www.facebook.com/v19.0/dialog/oauth" in fb_url
    assert "state=fb_state_456" in fb_url


@pytest.mark.asyncio
async def test_mongodb_metadata_fallback():
    """Test that MongoDB metadata service degrades gracefully when offline / unconfigured."""
    # When MongoDB is not connected in tests, operations return safe fallbacks without throwing
    saved = await save_social_metadata("test-acc-id", "instagram", {"followers": 100})
    assert isinstance(saved, bool)

    data = await get_social_metadata("test-acc-id")
    assert data is None or isinstance(data, dict)
