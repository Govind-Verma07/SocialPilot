"""
tests/test_teams.py
-------------------
Test suite for Team and Workspace management endpoints.
"""

import pytest
from app.models.enums import TeamMemberRole


def test_create_and_list_teams(client):
    """Test creating a workspace and listing user's workspaces."""
    # Register user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Team Owner",
            "email": "owner@example.com",
            "password": "Password123",
            "role": "marketing_team",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create team
    create_res = client.post(
        "/api/v1/teams",
        json={"name": "Alpha Marketing Workspace"},
        headers=headers,
    )
    assert create_res.status_code == 201
    team = create_res.json()
    assert team["name"] == "Alpha Marketing Workspace"
    assert team["is_owner"] is True
    assert team["member_count"] == 1
    assert team["members"][0]["email"] == "owner@example.com"
    assert team["members"][0]["role"] == "owner"

    # List teams
    list_res = client.get("/api/v1/teams", headers=headers)
    assert list_res.status_code == 200
    teams_list = list_res.json()
    assert len(teams_list) == 1
    assert teams_list[0]["id"] == team["id"]


def test_add_and_manage_team_members(client):
    """Test adding a member, updating their role, and removing them."""
    # 1. Register owner
    reg_owner = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Owner User",
            "email": "owner2@example.com",
            "password": "Password123",
            "role": "business_user",
        },
    )
    owner_token = reg_owner.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # 2. Register candidate member
    client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Member Candidate",
            "email": "candidate@example.com",
            "password": "Password123",
            "role": "content_creator",
        },
    )

    # 3. Create team
    team_res = client.post(
        "/api/v1/teams",
        json={"name": "Beta Workspace"},
        headers=owner_headers,
    )
    team_id = team_res.json()["id"]

    # 4. Add member
    add_res = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "candidate@example.com", "role": "member"},
        headers=owner_headers,
    )
    assert add_res.status_code == 201
    member = add_res.json()
    assert member["email"] == "candidate@example.com"
    assert member["role"] == "member"
    member_id = member["id"]

    # 5. Update member role to admin
    patch_res = client.patch(
        f"/api/v1/teams/{team_id}/members/{member_id}",
        json={"role": "admin"},
        headers=owner_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["role"] == "admin"

    # 6. Remove member
    del_res = client.delete(
        f"/api/v1/teams/{team_id}/members/{member_id}",
        headers=owner_headers,
    )
    assert del_res.status_code == 200

    # Verify team now has only 1 member
    get_res = client.get(f"/api/v1/teams/{team_id}", headers=owner_headers)
    assert get_res.status_code == 200
    assert get_res.json()["member_count"] == 1


def test_add_nonexistent_member_fails(client):
    """Test adding an unregistered email fails with 404."""
    reg_owner = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Owner 3",
            "email": "owner3@example.com",
            "password": "Password123",
            "role": "marketing_team",
        },
    )
    owner_headers = {"Authorization": f"Bearer {reg_owner.json()['access_token']}"}

    team_res = client.post(
        "/api/v1/teams",
        json={"name": "Gamma Workspace"},
        headers=owner_headers,
    )
    team_id = team_res.json()["id"]

    add_res = client.post(
        f"/api/v1/teams/{team_id}/members",
        json={"email": "nonexistent_person_123@example.com", "role": "member"},
        headers=owner_headers,
    )
    assert add_res.status_code == 404
    assert "The user must register first" in add_res.json()["detail"]
