"""
tests/test_phase2_calendar.py
-----------------------------
Automated test suite for Phase 2: Publishing Calendar.
Tests date range filtering, status filtering, multi-account display,
empty periods, authentication, and ownership isolation.
"""

from datetime import datetime, timedelta, timezone
from app.core.encryption import encrypt_token
from app.models.enums import AccountStatus, PostStatus, SocialPlatform
from app.models.post import Post
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
        platform_account_id=f"{platform.value}_id_999",
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
# TEST 1 — Calendar date range filtering
# ==============================================================================
def test_1_calendar_date_range_filter(client, db_session):
    """
    Create scheduled posts with different dates.
    Query for a specific date range.
    Expected: Only posts within the start_date and end_date range are returned.
    """
    user_id, _, headers = _register_and_login(client, "cal_user1@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn")

    base_time = datetime.now(timezone.utc).replace(microsecond=0)
    time_early = (base_time + timedelta(days=2)).isoformat()
    time_mid = (base_time + timedelta(days=10)).isoformat()
    time_late = (base_time + timedelta(days=25)).isoformat()

    # Create 3 posts on different dates
    client.post("/api/v1/posts", json={"content": "Post 1", "social_account_ids": [acc.id], "scheduled_at": time_early}, headers=headers)
    client.post("/api/v1/posts", json={"content": "Post 2", "social_account_ids": [acc.id], "scheduled_at": time_mid}, headers=headers)
    client.post("/api/v1/posts", json={"content": "Post 3", "social_account_ids": [acc.id], "scheduled_at": time_late}, headers=headers)

    # Filter window containing only Post 2 (days 5 to 15)
    query_start = (base_time + timedelta(days=5)).strftime("%Y-%m-%d")
    query_end = (base_time + timedelta(days=15)).strftime("%Y-%m-%d")

    res = client.get(f"/api/v1/posts?status=scheduled&start_date={query_start}&end_date={query_end}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 1
    assert data["items"][0]["content"] == "Post 2"


# ==============================================================================
# TEST 2 — Scheduled status filtering
# ==============================================================================
def test_2_calendar_status_filter(client, db_session):
    """
    Query with status=scheduled only returns scheduled posts.
    """
    user_id, _, headers = _register_and_login(client, "cal_user2@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "My Facebook")

    future_time = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()

    # 1. Scheduled post
    res_sched = client.post("/api/v1/posts", json={"content": "Scheduled Post", "social_account_ids": [acc.id], "scheduled_at": future_time}, headers=headers)
    assert res_sched.status_code == 201

    # 2. Draft post (created directly in DB for status check)
    draft_post = Post(
        user_id=user_id,
        content="Draft Post",
        status=PostStatus.draft.value,
        post_type="text",
    )
    db_session.add(draft_post)
    db_session.commit()

    # Query status=scheduled
    res = client.get("/api/v1/posts?status=scheduled", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert all(p["status"] == "scheduled" for p in items)
    assert any(p["content"] == "Scheduled Post" for p in items)
    assert not any(p["content"] == "Draft Post" for p in items)


# ==============================================================================
# TEST 3 — Multiple posts on different dates
# ==============================================================================
def test_3_multiple_posts_dates(client, db_session):
    """
    Create several posts across multiple days.
    Expected: All retrieved with correct scheduled_at timestamps.
    """
    user_id, _, headers = _register_and_login(client, "cal_user3@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.x, "X Feed")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    dates = [now + timedelta(days=i) for i in [1, 2, 3]]

    for idx, d in enumerate(dates):
        res = client.post(
            "/api/v1/posts",
            json={"content": f"Multi Post {idx + 1}", "social_account_ids": [acc.id], "scheduled_at": d.isoformat()},
            headers=headers,
        )
        assert res.status_code == 201

    res = client.get("/api/v1/posts?status=scheduled", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 3


# ==============================================================================
# TEST 4 — Multiple social accounts for calendar events
# ==============================================================================
def test_4_multiple_social_accounts_in_calendar(client, db_session):
    """
    Post associated with LinkedIn, Facebook, Instagram returns all accounts in calendar event payload.
    """
    user_id, _, headers = _register_and_login(client, "cal_user4@example.com")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "LI Acc")
    acc_fb = _seed_account(db_session, user_id, SocialPlatform.facebook, "FB Acc")
    acc_ig = _seed_account(db_session, user_id, SocialPlatform.instagram, "IG Acc")

    future_time = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()

    client.post(
        "/api/v1/posts",
        json={"content": "Omnichannel campaign", "social_account_ids": [acc_li.id, acc_fb.id, acc_ig.id], "scheduled_at": future_time},
        headers=headers,
    )

    res = client.get("/api/v1/posts?status=scheduled", headers=headers)
    assert res.status_code == 200
    post = res.json()["items"][0]
    platforms = {sa["platform"] for sa in post["social_accounts"]}
    assert platforms == {"linkedin", "facebook", "instagram"}


# ==============================================================================
# TEST 5 — Empty calendar range
# ==============================================================================
def test_5_empty_calendar_range(client):
    """
    Querying a date range with no posts returns total=0 and items=[].
    """
    _, _, headers = _register_and_login(client, "cal_user5@example.com")

    res = client.get("/api/v1/posts?status=scheduled&start_date=2040-01-01&end_date=2040-01-31", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


# ==============================================================================
# TEST 6 — Calendar unauthenticated request
# ==============================================================================
def test_6_calendar_unauthenticated_fails(client):
    """
    Unauthenticated request to calendar posts endpoint returns 401.
    """
    res = client.get("/api/v1/posts?start_date=2026-09-01&end_date=2026-09-30")
    assert res.status_code == 401


# ==============================================================================
# TEST 7 — Calendar user ownership isolation
# ==============================================================================
def test_7_calendar_ownership_isolation(client, db_session):
    """
    User A cannot retrieve User B's posts even when querying the exact same date range.
    """
    user_a_id, _, headers_a = _register_and_login(client, "cal_usera@example.com")
    user_b_id, _, headers_b = _register_and_login(client, "cal_userb@example.com")

    acc_a = _seed_account(db_session, user_a_id, SocialPlatform.linkedin, "User A LI")
    acc_b = _seed_account(db_session, user_b_id, SocialPlatform.linkedin, "User B LI")

    same_time = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    client.post("/api/v1/posts", json={"content": "User A secret post", "social_account_ids": [acc_a.id], "scheduled_at": same_time}, headers=headers_a)
    client.post("/api/v1/posts", json={"content": "User B secret post", "social_account_ids": [acc_b.id], "scheduled_at": same_time}, headers=headers_b)

    # User A queries
    res_a = client.get("/api/v1/posts?status=scheduled", headers=headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["total"] == 1
    assert res_a.json()["items"][0]["content"] == "User A secret post"

    # User B queries
    res_b = client.get("/api/v1/posts?status=scheduled", headers=headers_b)
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 1
    assert res_b.json()["items"][0]["content"] == "User B secret post"
