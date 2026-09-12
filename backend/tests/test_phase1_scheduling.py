"""
tests/test_phase1_scheduling.py
-------------------------------
Comprehensive automated test suite for Phase 1: Content Scheduling Foundation.
Tests all 8 required test scenarios from p1.txt:
  TEST 1: Create scheduled post (persisted in DB with status=SCHEDULED)
  TEST 2: Multiple connected social accounts associated with one post
  TEST 3: No content / whitespace-only content validation
  TEST 4: No social account selected validation
  TEST 5: Past schedule date/time validation
  TEST 6: Retrieve scheduled posts via GET /posts
  TEST 7: Unauthenticated request handling (401 Unauthorized)
  TEST 8: User isolation and ownership validation
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
        platform_account_id=f"{platform.value}_id_123",
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
# TEST 1 — Create Scheduled Post
# ==============================================================================
def test_1_create_scheduled_post(client, db_session):
    """
    Login → Create Post → Enter content → Select LinkedIn → Select future date/time → Schedule
    Expected: Post created successfully, DB status = SCHEDULED, scheduled_at = selected datetime.
    """
    user_id, _, headers = _register_and_login(client, "user1@example.com")
    linkedin_acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn Page")

    future_time = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)

    payload = {
        "content": "Hello from SocialPilot Phase 1!",
        "social_account_ids": [linkedin_acc.id],
        "scheduled_at": future_time.isoformat(),
        "post_type": "text",
    }

    res = client.post("/api/v1/posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["content"] == "Hello from SocialPilot Phase 1!"
    assert data["status"] == PostStatus.scheduled.value
    assert len(data["social_accounts"]) == 1
    assert data["social_accounts"][0]["id"] == linkedin_acc.id
    assert data["social_accounts"][0]["platform"] == "linkedin"

    # Verify directly in database
    db_post = db_session.query(Post).filter(Post.id == data["id"]).first()
    assert db_post is not None
    assert db_post.status == PostStatus.scheduled.value
    assert db_post.user_id == user_id
    assert len(db_post.social_accounts) == 1
    assert db_post.social_accounts[0].social_account_id == linkedin_acc.id


# ==============================================================================
# TEST 2 — Multiple Accounts
# ==============================================================================
def test_2_multiple_accounts(client, db_session):
    """
    Create a post and select: LinkedIn, Facebook, Instagram.
    Expected: One post created and all 3 social accounts associated with it.
    """
    user_id, _, headers = _register_and_login(client, "user2@example.com")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "LinkedIn Profile")
    acc_fb = _seed_account(db_session, user_id, SocialPlatform.facebook, "Facebook Page")
    acc_ig = _seed_account(db_session, user_id, SocialPlatform.instagram, "Instagram Account")

    future_time = (datetime.now(timezone.utc) + timedelta(days=5)).replace(microsecond=0)

    payload = {
        "content": "Cross-platform announcement across 3 channels!",
        "social_account_ids": [acc_li.id, acc_fb.id, acc_ig.id],
        "scheduled_at": future_time.isoformat(),
    }

    res = client.post("/api/v1/posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert len(data["social_accounts"]) == 3
    returned_ids = {a["id"] for a in data["social_accounts"]}
    assert returned_ids == {acc_li.id, acc_fb.id, acc_ig.id}

    # Verify junction table in DB
    links = db_session.query(PostSocialAccount).filter(PostSocialAccount.post_id == data["id"]).all()
    assert len(links) == 3


# ==============================================================================
# TEST 3 — No Content Validation
# ==============================================================================
def test_3_no_content_fails(client, db_session):
    """
    Try scheduling without content (or whitespace-only).
    Expected: Validation error. No database record should be created.
    """
    user_id, _, headers = _register_and_login(client, "user3@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.x, "Twitter Profile")
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    # Empty string
    r1 = client.post(
        "/api/v1/posts",
        json={"content": "", "social_account_ids": [acc.id], "scheduled_at": future_time},
        headers=headers,
    )
    assert r1.status_code in [400, 422]

    # Whitespace only
    r2 = client.post(
        "/api/v1/posts",
        json={"content": "    \n\t  ", "social_account_ids": [acc.id], "scheduled_at": future_time},
        headers=headers,
    )
    assert r2.status_code in [400, 422]

    # Ensure no post record in DB
    posts_count = db_session.query(Post).filter(Post.user_id == user_id).count()
    assert posts_count == 0


# ==============================================================================
# TEST 4 — No Social Account Validation
# ==============================================================================
def test_4_no_social_account_fails(client, db_session):
    """
    Try scheduling without selecting an account.
    Expected: Validation error.
    """
    user_id, _, headers = _register_and_login(client, "user4@example.com")
    future_time = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    res = client.post(
        "/api/v1/posts",
        json={"content": "Post without accounts", "social_account_ids": [], "scheduled_at": future_time},
        headers=headers,
    )
    assert res.status_code in [400, 422]


# ==============================================================================
# TEST 5 — Past Date Validation
# ==============================================================================
def test_5_past_date_fails(client, db_session):
    """
    Try scheduling for a past date/time.
    Expected: Validation error ('Scheduled time must be in the future.').
    """
    user_id, _, headers = _register_and_login(client, "user5@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.pinterest, "Pinterest Board")
    past_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

    res = client.post(
        "/api/v1/posts",
        json={"content": "Past post", "social_account_ids": [acc.id], "scheduled_at": past_time},
        headers=headers,
    )
    assert res.status_code in [400, 422]
    error_text = str(res.json())
    assert "Scheduled time must be in the future" in error_text


# ==============================================================================
# TEST 6 — Retrieve Scheduled Post
# ==============================================================================
def test_6_retrieve_scheduled_posts(client, db_session):
    """
    Create a scheduled post, then call GET /posts.
    Expected: Post appears with content, selected platform(s), scheduled datetime, SCHEDULED status.
    """
    user_id, _, headers = _register_and_login(client, "user6@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.youtube, "YouTube Channel")
    future_time = (datetime.now(timezone.utc) + timedelta(days=7)).replace(microsecond=0)

    # 1. Create scheduled post
    create_res = client.post(
        "/api/v1/posts",
        json={
            "content": "Exclusive YouTube premiere scheduled!",
            "social_account_ids": [acc.id],
            "scheduled_at": future_time.isoformat(),
        },
        headers=headers,
    )
    assert create_res.status_code == 201

    # 2. Retrieve posts list
    list_res = client.get("/api/v1/posts", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()

    assert data["total"] >= 1
    post_item = data["items"][0]
    assert post_item["content"] == "Exclusive YouTube premiere scheduled!"
    assert post_item["status"] == PostStatus.scheduled.value
    assert len(post_item["social_accounts"]) == 1
    assert post_item["social_accounts"][0]["platform"] == "youtube"


# ==============================================================================
# TEST 7 — Authentication
# ==============================================================================
def test_7_unauthenticated_access_fails(client):
    """
    Try calling the post API without valid authentication.
    Expected: 401 Unauthorized response.
    """
    # Create attempt without token
    r1 = client.post(
        "/api/v1/posts",
        json={"content": "Hacker post", "social_account_ids": ["dummy-id"], "scheduled_at": "2030-01-01T00:00:00Z"},
    )
    assert r1.status_code == 401

    # List attempt without token
    r2 = client.get("/api/v1/posts")
    assert r2.status_code == 401


# ==============================================================================
# TEST 8 — Ownership Isolation
# ==============================================================================
def test_8_ownership_isolation(client, db_session):
    """
    Verify that one user cannot attach another user's social account or access another user's posts.
    """
    # User A setup
    user_a_id, _, headers_a = _register_and_login(client, "usera@example.com")
    acc_a = _seed_account(db_session, user_a_id, SocialPlatform.linkedin, "User A LinkedIn")

    # User B setup
    user_b_id, _, headers_b = _register_and_login(client, "userb@example.com")

    future_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    # 1. User B tries to create a post using User A's account -> Must fail
    res_b_create = client.post(
        "/api/v1/posts",
        json={
            "content": "User B trying to use User A's account",
            "social_account_ids": [acc_a.id],
            "scheduled_at": future_time,
        },
        headers=headers_b,
    )
    assert res_b_create.status_code == 400
    assert "Selected social account is not available" in res_b_create.json()["detail"]

    # 2. User A creates a post
    res_a = client.post(
        "/api/v1/posts",
        json={
            "content": "User A private post",
            "social_account_ids": [acc_a.id],
            "scheduled_at": future_time,
        },
        headers=headers_a,
    )
    assert res_a.status_code == 201
    post_a_id = res_a.json()["id"]

    # 3. User B tries to view User A's specific post -> 403 Forbidden
    res_b_view = client.get(f"/api/v1/posts/{post_a_id}", headers=headers_b)
    assert res_b_view.status_code == 403

    # 4. User B lists posts -> Cannot see User A's post
    res_b_list = client.get("/api/v1/posts", headers=headers_b)
    assert res_b_list.status_code == 200
    assert res_b_list.json()["total"] == 0
