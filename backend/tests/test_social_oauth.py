"""
tests/test_social_oauth.py
--------------------------
Test suite for Social OAuth endpoints, platform discovery, and state token validation.
"""

import pytest
from app.core.config import settings
from app.models.enums import SocialPlatform


def test_list_platforms(client):
    """Test listing all 6 social media platforms."""
    response = client.get("/api/v1/social/platforms")
    assert response.status_code == 200
    platforms = response.json()
    assert len(platforms) == 6

    platform_names = {p["platform"] for p in platforms}
    expected = {"facebook", "instagram", "linkedin", "x", "youtube", "pinterest"}
    assert platform_names == expected

    for p in platforms:
        assert "display_name" in p
        assert "is_configured" in p
        assert "supported_permissions" in p
        assert "profile_read" in p["supported_permissions"]


def test_authorize_unconfigured_platform_returns_clear_message(client):
    """Test requesting auth URL for an unconfigured platform returns clean status without faking connection."""
    # Ensure credentials are empty for testing
    settings.FACEBOOK_CLIENT_ID = ""
    settings.FACEBOOK_CLIENT_SECRET = ""

    # Register & authenticate user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "OAuth Tester",
            "email": "oauth_tester@example.com",
            "password": "Password123",
            "role": "content_creator",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/social/oauth/facebook/authorize", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "facebook"
    assert data["is_configured"] is False
    assert data["authorization_url"] is None
    assert "awaiting" in data["message"].lower() or "not configured" in data["message"].lower()


def test_authorize_configured_platform_generates_valid_url(client):
    """Test requesting auth URL when credentials exist generates redirect URL with signed state."""
    # Temporarily set dummy test credentials
    settings.LINKEDIN_CLIENT_ID = "test_linkedin_client_id"
    settings.LINKEDIN_CLIENT_SECRET = "test_linkedin_client_secret"

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "LinkedIn User",
            "email": "linkedin_tester@example.com",
            "password": "Password123",
            "role": "business_user",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/v1/social/oauth/linkedin/authorize", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["platform"] == "linkedin"
    assert data["is_configured"] is True
    assert data["authorization_url"] is not None
    assert "linkedin.com/oauth/v2/authorization" in data["authorization_url"]
    assert "state=" in data["authorization_url"]


def test_oauth_callback_error_redirects_to_frontend(client):
    """Test that platform errors during callback redirect to frontend /accounts with error message."""
    res = client.get(
        "/api/v1/social/oauth/facebook/callback?error=access_denied&error_description=User+canceled+login",
        follow_redirects=False,
    )
    assert res.status_code in [302, 307]
    location = res.headers["location"]
    assert "/accounts" in location
    assert "error=" in location
