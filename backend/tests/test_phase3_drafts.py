"""
tests/test_phase3_drafts.py
---------------------------
Automated test suite for Phase 3: Draft Post Lifecycle.
Tests creating drafts, retrieving drafts, editing drafts, converting
DRAFT -> SCHEDULED, validation on conversion, deletion, authentication,
and ownership protection.
"""

from datetime import datetime, timedelta, timezone
from app.core.encryption import encrypt_token
from app.models.enums import AccountStatus, PostStatus, SocialPlatform
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount


def _register_and_login(client, email: str, name: str = "Test User") -> tuple[str, str, dict]:
    """Helper to register and return (user_id, token, auth_headers)."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": "Password123",
        },
    )
    assert res.status_code == 201
    data = res.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, token, headers


def _seed_account(db_session, user_id: str, platform: SocialPlatform, name: str) -> SocialAccount:
    """Helper to create a connected social account in DB."""
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_id_draft",
        account_name=name,
        account_username=f"{platform.value}_handle",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("mock_token_secret"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


# ==============================================================================
# TEST 1 — Create Draft
# ==============================================================================
def test_1_create_draft(client, db_session):
    """
    Create a post with status = DRAFT.
    Expected: HTTP success (201). Database contains draft.
    """
    user_id, _, headers = _register_and_login(client, "draft_user1@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "User 1 LinkedIn")

    payload = {
        "content": "Work in progress draft...",
        "social_account_ids": [acc.id],
        "status": "draft",
        "post_type": "text",
    }

    res = client.post("/api/v1/posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["content"] == "Work in progress draft..."
    assert data["status"] == "draft"
    assert data["scheduled_at"] is None
    assert len(data["social_accounts"]) == 1

    # Verify directly in DB
    db_post = db_session.query(Post).filter(Post.id == data["id"]).first()
    assert db_post is not None
    assert db_post.status == PostStatus.draft.value
    assert db_post.user_id == user_id


# ==============================================================================
# TEST 2 — Retrieve Drafts
# ==============================================================================
def test_2_retrieve_drafts(client, db_session):
    """
    Create multiple drafts. Call GET /posts?status=draft.
    Expected: Only authenticated user's drafts are returned.
    """
    user_id, _, headers = _register_and_login(client, "draft_user2@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "User 2 Facebook")

    # Create 2 drafts
    client.post("/api/v1/posts", json={"content": "Draft Alpha", "status": "draft"}, headers=headers)
    client.post("/api/v1/posts", json={"content": "Draft Beta", "status": "draft"}, headers=headers)

    # Create 1 scheduled post
    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    client.post("/api/v1/posts", json={"content": "Scheduled Gamma", "social_account_ids": [acc.id], "scheduled_at": future_time, "status": "scheduled"}, headers=headers)

    res = client.get("/api/v1/posts?status=draft", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 2
    contents = {item["content"] for item in data["items"]}
    assert contents == {"Draft Alpha", "Draft Beta"}
    assert all(item["status"] == "draft" for item in data["items"])


# ==============================================================================
# TEST 3 — Edit Draft
# ==============================================================================
def test_3_edit_draft(client, db_session):
    """
    Create draft: 'Old content'. Update to: 'Updated content'.
    Expected: Database contains updated content. Status remains DRAFT.
    """
    user_id, _, headers = _register_and_login(client, "draft_user3@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.x, "User 3 X")

    # 1. Create initial draft
    res_create = client.post("/api/v1/posts", json={"content": "Old content", "status": "draft"}, headers=headers)
    assert res_create.status_code == 201
    draft_id = res_create.json()["id"]

    # 2. Update draft
    res_update = client.put(
        f"/api/v1/posts/{draft_id}",
        json={
            "content": "Updated content with hashtags #SocialPilot",
            "social_account_ids": [acc.id],
            "status": "draft",
        },
        headers=headers,
    )
    assert res_update.status_code == 200
    data = res_update.json()

    assert data["content"] == "Updated content with hashtags #SocialPilot"
    assert data["status"] == "draft"
    assert len(data["social_accounts"]) == 1

    # Verify DB
    db_post = db_session.query(Post).filter(Post.id == draft_id).first()
    assert db_post.content == "Updated content with hashtags #SocialPilot"
    assert db_post.status == PostStatus.draft.value


# ==============================================================================
# TEST 4 — Draft → Scheduled Conversion
# ==============================================================================
def test_4_convert_draft_to_scheduled(client, db_session):
    """
    Create draft. Update with valid content, valid account, and future scheduled time.
    Expected: DRAFT → SCHEDULED. No duplicate post is created.
    """
    user_id, _, headers = _register_and_login(client, "draft_user4@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "User 4 LinkedIn")

    # 1. Create draft
    res_create = client.post("/api/v1/posts", json={"content": "Draft to convert", "status": "draft"}, headers=headers)
    assert res_create.status_code == 201
    draft_id = res_create.json()["id"]

    total_posts_before = db_session.query(Post).count()

    # 2. Convert DRAFT -> SCHEDULED
    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    res_schedule = client.put(
        f"/api/v1/posts/{draft_id}",
        json={
            "content": "Finalized content ready for scheduling",
            "social_account_ids": [acc.id],
            "scheduled_at": future_time,
            "status": "scheduled",
        },
        headers=headers,
    )
    assert res_schedule.status_code == 200
    data = res_schedule.json()

    assert data["id"] == draft_id
    assert data["status"] == "scheduled"
    assert data["content"] == "Finalized content ready for scheduling"

    # Verify no duplicate post was created
    total_posts_after = db_session.query(Post).count()
    assert total_posts_after == total_posts_before

    # Verify it is no longer returned in drafts
    res_drafts = client.get("/api/v1/posts?status=draft", headers=headers)
    assert res_drafts.json()["total"] == 0

    # Verify it is returned in scheduled posts
    res_sched = client.get("/api/v1/posts?status=scheduled", headers=headers)
    assert res_sched.json()["total"] == 1
    assert res_sched.json()["items"][0]["id"] == draft_id


# ==============================================================================
# TEST 5 — Invalid Draft Scheduling Validation
# ==============================================================================
def test_5_invalid_draft_scheduling_fails(client, db_session):
    """
    Try to schedule a draft with empty content, no social account, or past scheduled time.
    Expected: Validation failure (400). Draft remains a draft.
    """
    user_id, _, headers = _register_and_login(client, "draft_user5@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.instagram, "User 5 Instagram")

    # Create draft
    res_create = client.post("/api/v1/posts", json={"content": "My Draft", "status": "draft"}, headers=headers)
    assert res_create.status_code == 201
    draft_id = res_create.json()["id"]

    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    past_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    # Case A: Empty content
    r1 = client.put(
        f"/api/v1/posts/{draft_id}",
        json={"content": "   ", "social_account_ids": [acc.id], "scheduled_at": future_time, "status": "scheduled"},
        headers=headers,
    )
    assert r1.status_code == 400

    # Case B: No social accounts
    r2 = client.put(
        f"/api/v1/posts/{draft_id}",
        json={"content": "Valid text", "social_account_ids": [], "scheduled_at": future_time, "status": "scheduled"},
        headers=headers,
    )
    assert r2.status_code == 400

    # Case C: Past scheduled time
    r3 = client.put(
        f"/api/v1/posts/{draft_id}",
        json={"content": "Valid text", "social_account_ids": [acc.id], "scheduled_at": past_time, "status": "scheduled"},
        headers=headers,
    )
    assert r3.status_code == 400

    # Verify draft remains DRAFT in DB
    db_post = db_session.query(Post).filter(Post.id == draft_id).first()
    assert db_post.status == PostStatus.draft.value


# ==============================================================================
# TEST 6 — Delete Draft
# ==============================================================================
def test_6_delete_draft(client, db_session):
    """
    Create draft. Delete it.
    Expected: Draft is no longer returned in DB or API.
    """
    user_id, _, headers = _register_and_login(client, "draft_user6@example.com")

    res_create = client.post("/api/v1/posts", json={"content": "Draft to delete", "status": "draft"}, headers=headers)
    assert res_create.status_code == 201
    draft_id = res_create.json()["id"]

    # Delete draft
    res_del = client.delete(f"/api/v1/posts/{draft_id}", headers=headers)
    assert res_del.status_code == 200

    # Confirm it cannot be retrieved
    res_get = client.get(f"/api/v1/posts/{draft_id}", headers=headers)
    assert res_get.status_code == 404

    res_list = client.get("/api/v1/posts?status=draft", headers=headers)
    assert res_list.json()["total"] == 0


# ==============================================================================
# TEST 7 — Authentication
# ==============================================================================
def test_7_unauthenticated_draft_operations_fail(client):
    """
    Unauthenticated user attempts draft operations -> 401 Unauthorized.
    """
    # Create draft
    r1 = client.post("/api/v1/posts", json={"content": "Draft", "status": "draft"})
    assert r1.status_code == 401

    # Update draft
    r2 = client.put("/api/v1/posts/dummy-id", json={"content": "Updated", "status": "draft"})
    assert r2.status_code == 401


# ==============================================================================
# TEST 8 — Ownership Isolation
# ==============================================================================
def test_8_draft_ownership_isolation(client, db_session):
    """
    User A attempts to access, edit, or delete User B's draft -> 403 Forbidden.
    """
    user_a_id, _, headers_a = _register_and_login(client, "draft_usera@example.com")
    user_b_id, _, headers_b = _register_and_login(client, "draft_userb@example.com")

    # User B creates a draft
    res_b = client.post("/api/v1/posts", json={"content": "User B secret draft", "status": "draft"}, headers=headers_b)
    assert res_b.status_code == 201
    draft_b_id = res_b.json()["id"]

    # User A tries to view User B's draft -> 403
    r_view = client.get(f"/api/v1/posts/{draft_b_id}", headers=headers_a)
    assert r_view.status_code == 403

    # User A tries to update User B's draft -> 403
    r_edit = client.put(f"/api/v1/posts/{draft_b_id}", json={"content": "Hacked content", "status": "draft"}, headers=headers_a)
    assert r_edit.status_code == 403

    # User A tries to delete User B's draft -> 403
    r_del = client.delete(f"/api/v1/posts/{draft_b_id}", headers=headers_a)
    assert r_del.status_code == 403

    # User A lists drafts -> total = 0
    r_list = client.get("/api/v1/posts?status=draft", headers=headers_a)
    assert r_list.json()["total"] == 0
