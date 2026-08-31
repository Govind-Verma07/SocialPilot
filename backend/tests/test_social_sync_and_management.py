"""
tests/test_social_sync_and_management.py
----------------------------------------
Test suite for multi-account listing, synchronization, permissions, and disconnect.
"""

from datetime import datetime, timedelta, timezone
import pytest
from app.core.encryption import encrypt_token
from app.models.enums import AccountStatus, SocialPlatform, SyncStatus
from app.models.social_account import AccountPermission, AccountSyncLog, SocialAccount


def test_social_account_full_lifecycle(client, db_session):
    """Test creating an account, listing (verifying tokens are hidden), syncing, permissions, and disconnect."""
    # 1. Register & login user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Social Manager",
            "email": "manager@example.com",
            "password": "Password123",
            "role": "marketing_team",
        },
    )
    user_id = reg.json()["user"]["id"]
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Seed a connected social account with encrypted tokens and permissions
    now = datetime.now(timezone.utc)
    account = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.x.value,
        platform_account_id="x_1234567",
        account_name="Marketing Team X",
        account_username="marketing_team_x",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("plain_oauth_token_secret_123"),
        token_expires_at=now + timedelta(days=30),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    perm1 = AccountPermission(social_account_id=account.id, permission="profile_read", granted=True)
    perm2 = AccountPermission(social_account_id=account.id, permission="content_publish", granted=True)
    db_session.add_all([perm1, perm2])
    db_session.commit()

    # 3. List accounts — verify tokens are completely hidden from API response
    list_res = client.get("/api/v1/social/accounts", headers=headers)
    assert list_res.status_code == 200
    accounts = list_res.json()
    assert len(accounts) == 1
    acc = accounts[0]
    assert acc["platform"] == "x"
    assert acc["account_username"] == "marketing_team_x"
    assert acc["status"] == "connected"
    assert len(acc["permissions"]) == 2
    assert "access_token_encrypted" not in acc
    assert "refresh_token_encrypted" not in acc
    assert "plain_oauth_token_secret_123" not in str(acc)

    # 4. Sync account
    sync_res = client.post(f"/api/v1/social/accounts/{account.id}/sync", headers=headers)
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["status"] == "success"
    assert "synchronized successfully" in sync_data["message"]

    # 5. Check permissions endpoint
    perms_res = client.get(f"/api/v1/social/accounts/{account.id}/permissions", headers=headers)
    assert perms_res.status_code == 200
    perms = perms_res.json()
    assert len(perms) == 2
    perm_names = {p["permission"] for p in perms}
    assert perm_names == {"profile_read", "content_publish"}

    # 6. Disconnect account
    del_res = client.delete(f"/api/v1/social/accounts/{account.id}", headers=headers)
    assert del_res.status_code == 200
    assert "Successfully disconnected" in del_res.json()["message"]

    # Verify account is gone
    list_after = client.get("/api/v1/social/accounts", headers=headers)
    assert list_after.status_code == 200
    assert len(list_after.json()) == 0


def test_sync_expired_token_handling(client, db_session):
    """Test sync on an expired token flags the account as token_expired."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Expired Tester",
            "email": "expired@example.com",
            "password": "Password123",
            "role": "content_creator",
        },
    )
    user_id = reg.json()["user"]["id"]
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Seed account with expired timestamp in the past
    past = datetime.now(timezone.utc) - timedelta(days=5)
    account = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_9999",
        account_name="Expired FB Page",
        account_username="expired_page",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("old_token"),
        token_expires_at=past,
        connected_at=past,
    )
    db_session.add(account)
    db_session.commit()

    sync_res = client.post(f"/api/v1/social/accounts/{account.id}/sync", headers=headers)
    assert sync_res.status_code == 200
    data = sync_res.json()
    assert data["status"] == "failed"
    assert "expired" in data["message"].lower()

    # Verify DB status updated to token_expired
    get_res = client.get(f"/api/v1/social/accounts/{account.id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "token_expired"
