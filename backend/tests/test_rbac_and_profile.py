"""
tests/test_rbac_and_profile.py
------------------------------
Test suite for RBAC validation, User Profile, and User Settings.
"""

import pytest
from app.models.enums import UserRole


def test_public_registration_allowed_roles(client):
    """Test that public registration accepts content_creator, marketing_team, and business_user."""
    roles = ["content_creator", "marketing_team", "business_user"]
    for role in roles:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "full_name": f"{role.title()} User",
                "email": f"{role}@example.com",
                "password": "Password123",
                "role": role,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["user"]["role"] == role


def test_public_registration_blocks_administrator(client):
    """Test that public registration explicitly rejects the administrator role."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Admin User",
            "email": "admin@example.com",
            "password": "Password123",
            "role": "administrator",
        },
    )
    assert response.status_code == 422


def test_update_profile(client):
    """Test updating user profile (full_name)."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Original Name",
            "email": "update_me@example.com",
            "password": "Password123",
            "role": "content_creator",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Update full_name
    patch_res = client.patch(
        "/api/v1/users/me",
        json={"full_name": "Updated Name"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["full_name"] == "Updated Name"

    # Verify GET /users/me
    get_res = client.get("/api/v1/users/me", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["full_name"] == "Updated Name"


def test_user_settings_lifecycle(client):
    """Test retrieving and updating user settings."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Settings User",
            "email": "settings_user@example.com",
            "password": "Password123",
            "role": "business_user",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # GET default settings
    get_res = client.get("/api/v1/users/me/settings", headers=headers)
    assert get_res.status_code == 200
    settings = get_res.json()
    assert settings["timezone"] == "UTC"
    assert settings["email_notifications"] is True

    # PUT update settings
    put_res = client.put(
        "/api/v1/users/me/settings",
        json={"timezone": "America/New_York", "email_notifications": False},
        headers=headers,
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["timezone"] == "America/New_York"
    assert updated["email_notifications"] is False


def test_rbac_require_roles_helper(client):
    """Test RBAC require_roles dependency rejecting unauthorized roles and allowing authorized roles."""
    from fastapi import APIRouter, Depends
    from app.services.auth_service import require_roles
    from app.main import app

    test_router = APIRouter()

    @test_router.get("/admin-only")
    def admin_only_route(user=Depends(require_roles([UserRole.administrator]))):
        return {"msg": "admin access granted"}

    @test_router.get("/creator-only")
    def creator_only_route(user=Depends(require_roles([UserRole.content_creator]))):
        return {"msg": "creator access granted"}

    app.include_router(test_router, prefix="/api/v1/test-rbac")

    # Register as content_creator
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Creator User",
            "email": "creator_rbac@example.com",
            "password": "Password123",
            "role": "content_creator",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Should succeed on creator-only
    res_creator = client.get("/api/v1/test-rbac/creator-only", headers=headers)
    assert res_creator.status_code == 200
    assert res_creator.json()["msg"] == "creator access granted"

    # Should be forbidden on admin-only (403)
    res_admin = client.get("/api/v1/test-rbac/admin-only", headers=headers)
    assert res_admin.status_code == 403
    assert "insufficient permissions" in res_admin.json()["detail"]

