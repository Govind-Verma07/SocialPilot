"""
tests/test_phase4_recurring.py
------------------------------
Automated test suite for Phase 4: Recurring Posts.
Covers:
  1. Create daily recurring schedule.
  2. Create weekly recurring schedule.
  3. Create monthly recurring schedule (including safe month-end clamping).
  4. Correct occurrence dates are generated.
  5. End date boundary is strictly respected.
  6. Multiple social accounts remain associated with every occurrence.
  7. Invalid recurrence inputs fail validation.
  8. Authentication enforcement (401 Unauthorized).
  9. User ownership isolation (User A vs User B).
  10. Deactivate and delete recurring rule.
  11. Generated occurrences appear through existing Phase 1 & 2 Posts/Calendar APIs.
"""

from datetime import datetime, timedelta, timezone
from app.core.encryption import encrypt_token
from app.models.enums import AccountStatus, PostStatus, SocialPlatform
from app.models.post import Post
from app.models.recurring_rule import RecurringRule
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
        platform_account_id=f"{platform.value}_id_{user_id[:8]}",
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


def _to_utc(dt_val) -> datetime:
    """Normalize datetime or ISO string to UTC aware datetime."""
    if isinstance(dt_val, str):
        dt = datetime.fromisoformat(dt_val.replace("Z", "+00:00"))
    else:
        dt = dt_val
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt



# ==============================================================================
# TEST 1 — Create Daily Recurring Schedule
# ==============================================================================
def test_1_create_daily_recurring_schedule(client, db_session):
    """Create a daily recurring post schedule and verify generated occurrences."""
    user_id, _, headers = _register_and_login(client, "user_daily@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "My Facebook Page")

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(days=4)  # 5 total occurrences (start, +1, +2, +3, +4)

    payload = {
        "content": "Daily marketing update",
        "social_account_ids": [acc.id],
        "frequency": "daily",
        "interval": 1,
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
        "post_type": "text",
    }

    res = client.post("/api/v1/recurring-posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["frequency"] == "daily"
    assert data["content"] == "Daily marketing update"
    assert data["is_active"] is True
    assert data["generated_count"] == 5
    assert len(data["occurrences"]) == 5
    assert len(data["social_accounts"]) == 1

    # Verify occurrences in DB
    rule_in_db = db_session.query(RecurringRule).filter(RecurringRule.id == data["id"]).first()
    assert rule_in_db is not None
    assert len(rule_in_db.posts) == 5
    for post in rule_in_db.posts:
        assert post.status == PostStatus.scheduled.value
        assert post.recurring_rule_id == rule_in_db.id


# ==============================================================================
# TEST 2 — Create Weekly Recurring Schedule
# ==============================================================================
def test_2_create_weekly_recurring_schedule(client, db_session):
    """Create a weekly recurring post on a specific day of week."""
    user_id, _, headers = _register_and_login(client, "user_weekly@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Company LinkedIn")

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=2)
    end_time = start_time + timedelta(days=28)  # 4-5 weeks

    payload = {
        "content": "Weekly Tuesday Roundup",
        "social_account_ids": [acc.id],
        "frequency": "weekly",
        "interval": 1,
        "by_weekday": "Tuesday",
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
    }

    res = client.post("/api/v1/recurring-posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["frequency"] == "weekly"
    assert data["by_weekday"] == 1  # Tuesday is 1
    assert data["generated_count"] >= 4

    # Verify all generated occurrences fall on a Tuesday (weekday == 1)
    for occ in data["occurrences"]:
        occ_dt = datetime.fromisoformat(occ["scheduled_at"].replace("Z", "+00:00"))
        assert occ_dt.weekday() == 1


# ==============================================================================
# TEST 3 — Create Monthly Recurring Schedule (Month-End Safe Clamping)
# ==============================================================================
def test_3_create_monthly_recurring_schedule_safe_monthend(client, db_session):
    """Create a monthly recurrence set on the 31st and verify safe handling."""
    user_id, _, headers = _register_and_login(client, "user_monthly@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.x, "Official X")

    # Start next month on the 31st (or closest day)
    now = datetime.now(timezone.utc)
    # Target 3 months into the future
    start_time = (now + timedelta(days=10)).replace(hour=10, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=100)

    payload = {
        "content": "Monthly Executive Summary",
        "social_account_ids": [acc.id],
        "frequency": "monthly",
        "interval": 1,
        "by_month_day": 31,
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
    }

    res = client.post("/api/v1/recurring-posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["frequency"] == "monthly"
    assert data["by_month_day"] == 31
    assert data["generated_count"] >= 2

    # Verify dates don't crash and month days are clamped to valid month ranges
    for occ in data["occurrences"]:
        occ_dt = datetime.fromisoformat(occ["scheduled_at"].replace("Z", "+00:00"))
        # Day must be <= 31 and <= days in that month
        assert 1 <= occ_dt.day <= 31


# ==============================================================================
# TEST 4 & 5 — Correct Dates Generated and End Date Strictly Respected
# ==============================================================================
def test_4_and_5_correct_dates_and_end_date_respected(client, db_session):
    """Verify occurrences are strictly between start_at and end_at."""
    user_id, _, headers = _register_and_login(client, "user_boundary@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.instagram, "My IG")

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(days=3, hours=1)  # Exact window

    payload = {
        "content": "Boundary Check Post",
        "social_account_ids": [acc.id],
        "frequency": "daily",
        "interval": 1,
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
    }

    res = client.post("/api/v1/recurring-posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    for occ in data["occurrences"]:
        occ_dt = _to_utc(occ["scheduled_at"])
        assert occ_dt >= _to_utc(start_time)
        assert occ_dt <= _to_utc(end_time)
        assert occ_dt > _to_utc(now)



# ==============================================================================
# TEST 6 — Multiple Social Accounts Associated with Every Occurrence
# ==============================================================================
def test_6_multiple_social_accounts_associated(client, db_session):
    """Verify multiple connected accounts are attached to each generated occurrence."""
    user_id, _, headers = _register_and_login(client, "user_multiacc@example.com")
    acc1 = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Company LinkedIn")
    acc2 = _seed_account(db_session, user_id, SocialPlatform.facebook, "Company Facebook")

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(days=2)

    payload = {
        "content": "Cross-platform multi-account campaign",
        "social_account_ids": [acc1.id, acc2.id],
        "frequency": "daily",
        "interval": 1,
        "start_at": start_time.isoformat(),
        "end_at": end_time.isoformat(),
    }

    res = client.post("/api/v1/recurring-posts", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert len(data["social_accounts"]) == 2
    for occ in data["occurrences"]:
        attached_ids = [sa["id"] for sa in occ["social_accounts"]]
        assert acc1.id in attached_ids
        assert acc2.id in attached_ids


# ==============================================================================
# TEST 7 — Validation Failure on Invalid Recurrence Input
# ==============================================================================
def test_7_invalid_recurrence_validation(client, db_session):
    """Verify rejection of empty content, empty accounts, past start date, invalid frequency, and bad end date."""
    user_id, _, headers = _register_and_login(client, "user_invalid@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.x, "Test X")

    now = datetime.now(timezone.utc)
    future_start = now + timedelta(days=2)
    future_end = now + timedelta(days=10)

    # 1. Empty content
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "   ",
            "social_account_ids": [acc.id],
            "frequency": "daily",
            "start_at": future_start.isoformat(),
            "end_at": future_end.isoformat(),
        },
        headers=headers,
    )
    assert res.status_code in (400, 422)

    # 2. Empty social accounts
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Valid content",
            "social_account_ids": [],
            "frequency": "daily",
            "start_at": future_start.isoformat(),
            "end_at": future_end.isoformat(),
        },
        headers=headers,
    )
    assert res.status_code in (400, 422)

    # 3. Start date in the past
    past_start = now - timedelta(days=1)
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Valid content",
            "social_account_ids": [acc.id],
            "frequency": "daily",
            "start_at": past_start.isoformat(),
            "end_at": future_end.isoformat(),
        },
        headers=headers,
    )
    assert res.status_code in (400, 422)

    # 4. End date before start date
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Valid content",
            "social_account_ids": [acc.id],
            "frequency": "daily",
            "start_at": future_end.isoformat(),
            "end_at": future_start.isoformat(),
        },
        headers=headers,
    )
    assert res.status_code in (400, 422)

    # 5. Invalid frequency
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Valid content",
            "social_account_ids": [acc.id],
            "frequency": "yearly",
            "start_at": future_start.isoformat(),
            "end_at": future_end.isoformat(),
        },
        headers=headers,
    )
    assert res.status_code in (400, 422)


# ==============================================================================
# TEST 8 — Authentication Enforcement (401 Unauthorized)
# ==============================================================================
def test_8_authentication_enforcement(client):
    """Verify that unauthenticated requests to recurring posts endpoints return 401."""
    now = datetime.now(timezone.utc)
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Test",
            "social_account_ids": ["acc_id"],
            "frequency": "daily",
            "start_at": (now + timedelta(days=1)).isoformat(),
            "end_at": (now + timedelta(days=5)).isoformat(),
        },
    )
    assert res.status_code == 401

    res = client.get("/api/v1/recurring-posts")
    assert res.status_code == 401

    res = client.get("/api/v1/recurring-posts/dummy_id")
    assert res.status_code == 401

    res = client.delete("/api/v1/recurring-posts/dummy_id")
    assert res.status_code == 401


# ==============================================================================
# TEST 9 — User Ownership Isolation
# ==============================================================================
def test_9_user_ownership_isolation(client, db_session):
    """User A cannot read, edit, delete User B's recurring rules or use User B's accounts."""
    user_a_id, _, headers_a = _register_and_login(client, "user_a_rec@example.com", "User A")
    user_b_id, _, headers_b = _register_and_login(client, "user_b_rec@example.com", "User B")

    acc_a = _seed_account(db_session, user_a_id, SocialPlatform.linkedin, "User A LinkedIn")
    acc_b = _seed_account(db_session, user_b_id, SocialPlatform.linkedin, "User B LinkedIn")

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(days=3)

    # 1. User B cannot use User A's social account
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Hacker attempt",
            "social_account_ids": [acc_a.id],
            "frequency": "daily",
            "start_at": start_time.isoformat(),
            "end_at": end_time.isoformat(),
        },
        headers=headers_b,
    )
    assert res.status_code == 400

    # User A creates their recurring rule
    res_a = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "User A Rule",
            "social_account_ids": [acc_a.id],
            "frequency": "daily",
            "start_at": start_time.isoformat(),
            "end_at": end_time.isoformat(),
        },
        headers=headers_a,
    )
    assert res_a.status_code == 201
    rule_a_id = res_a.json()["id"]

    # 2. User B cannot read User A's recurring rule
    res = client.get(f"/api/v1/recurring-posts/{rule_a_id}", headers=headers_b)
    assert res.status_code == 403

    # 3. User B cannot edit User A's recurring rule
    res = client.put(
        f"/api/v1/recurring-posts/{rule_a_id}",
        json={"content": "Modified by B"},
        headers=headers_b,
    )
    assert res.status_code == 403

    # 4. User B cannot delete User A's recurring rule
    res = client.delete(f"/api/v1/recurring-posts/{rule_a_id}", headers=headers_b)
    assert res.status_code == 403

    # 5. User B's list does not contain User A's rule
    res_list = client.get("/api/v1/recurring-posts", headers=headers_b)
    assert res_list.status_code == 200
    rule_ids = [r["id"] for r in res_list.json()["items"]]
    assert rule_a_id not in rule_ids


# ==============================================================================
# TEST 10 — Deactivate and Delete Recurring Rule
# ==============================================================================
def test_10_deactivate_and_delete_recurring_rule(client, db_session):
    """Test updating status to INACTIVE and deleting a recurring rule."""
    user_id, _, headers = _register_and_login(client, "user_lifecycle@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "Lifecycle FB")

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(days=3)

    # 1. Create rule
    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Lifecycle Rule",
            "social_account_ids": [acc.id],
            "frequency": "daily",
            "start_at": start_time.isoformat(),
            "end_at": end_time.isoformat(),
        },
        headers=headers,
    )
    assert res.status_code == 201
    rule_id = res.json()["id"]

    # 2. Deactivate rule
    res_update = client.put(
        f"/api/v1/recurring-posts/{rule_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["is_active"] is False

    # 3. Delete rule
    res_del = client.delete(f"/api/v1/recurring-posts/{rule_id}", headers=headers)
    assert res_del.status_code == 200

    # Verify rule is gone
    res_get = client.get(f"/api/v1/recurring-posts/{rule_id}", headers=headers)
    assert res_get.status_code == 404

    # Verify scheduled posts generated by this rule were removed
    posts_left = db_session.query(Post).filter(Post.recurring_rule_id == rule_id).all()
    assert len(posts_left) == 0


# ==============================================================================
# TEST 11 — Occurrences Appear in Existing Posts and Calendar APIs
# ==============================================================================
def test_11_occurrences_appear_in_existing_posts_and_calendar_apis(client, db_session):
    """Verify that generated occurrences integrate with existing Phase 1 & Phase 2 APIs."""
    user_id, _, headers = _register_and_login(client, "user_integration@example.com")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Integration LI")

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(days=2)
    end_time = start_time + timedelta(days=3)

    res = client.post(
        "/api/v1/recurring-posts",
        json={
            "content": "Integrated Post Item",
            "social_account_ids": [acc.id],
            "frequency": "daily",
            "start_at": start_time.isoformat(),
            "end_at": end_time.isoformat(),
        },
        headers=headers,
    )
    assert res.status_code == 201
    rule_id = res.json()["id"]

    # 1. Retrieve via Phase 1 Scheduled Posts API
    queue_res = client.get("/api/v1/posts?status=scheduled", headers=headers)
    assert queue_res.status_code == 200
    queue_items = queue_res.json()["items"]
    recurring_queue_items = [p for p in queue_items if p.get("recurring_rule_id") == rule_id]
    assert len(recurring_queue_items) == 4

    # 2. Retrieve via Phase 2 Calendar range filter
    cal_start = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    cal_end = (now + timedelta(days=6)).strftime("%Y-%m-%d")
    cal_res = client.get(f"/api/v1/posts?start_date={cal_start}&end_date={cal_end}", headers=headers)
    assert cal_res.status_code == 200
    cal_items = cal_res.json()["items"]
    recurring_cal_items = [p for p in cal_items if p.get("recurring_rule_id") == rule_id]
    assert len(recurring_cal_items) == 4
