"""
tests/test_phase6_automated_publishing.py
-----------------------------------------
Automated test suite for Phase 6: Automated Social Media Publishing.

Covers:
TEST 1: Scheduled future post is NOT selected
TEST 2: Due scheduled post is selected
TEST 3: Draft is NOT selected
TEST 4: Published post is NOT selected
TEST 5: Due post is atomically claimed (SCHEDULED -> PUBLISHING)
TEST 6: Publishing service is called
TEST 7: Successful publishing changes status appropriately (PUBLISHED)
TEST 8: Publishing failure changes status to FAILED
TEST 9: Multiple platform publishing works through existing Phase 5 service
TEST 10: Recurring-post generated occurrence is eligible for automatic publishing
TEST 11: Ownership / isolation rules remain intact
TEST 12 (Mandatory): Duplicate publish protection (Worker A claims, Worker B skips)
"""

from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta
import httpx

from app.models.enums import PostStatus, SocialPlatform, AccountStatus, RecurrenceFrequency
from app.models.post import Post, PostSocialAccount
from app.models.recurring_rule import RecurringRule, RecurringRuleSocialAccount
from app.models.social_account import SocialAccount
from app.core.encryption import encrypt_token
from app.worker.tasks import (
    get_due_posts_query,
    claim_post_for_publishing,
    process_due_post,
)


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


def _seed_account(db_session, user_id: str, platform: SocialPlatform, name: str, token: str = "mock-secret-token") -> SocialAccount:
    """Helper to create a connected social account in DB."""
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_acc_{user_id[:6]}",
        account_name=name,
        account_username=f"{platform.value}_handle",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token(token) if token else None,
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


# ==============================================================================
# TEST 1 — Scheduled Future Post Should NOT Be Selected
# ==============================================================================
def test_1_future_post_not_selected(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_future@test.com", "Future User")
    now_utc = datetime.now(timezone.utc)

    # Post scheduled 1 hour in the future
    post = Post(
        user_id=user_id,
        content="Post in the future",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(hours=1),
    )
    db_session.add(post)
    db_session.commit()

    due_posts = get_due_posts_query(db_session, now_utc).all()
    due_ids = [p.id for p in due_posts]
    assert post.id not in due_ids


# ==============================================================================
# TEST 2 — Due Scheduled Post Should Be Selected
# ==============================================================================
def test_2_due_scheduled_post_selected(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_due@test.com", "Due User")
    now_utc = datetime.now(timezone.utc)

    # Post scheduled 5 minutes in the past
    post = Post(
        user_id=user_id,
        content="Post that is due right now",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=5),
    )
    db_session.add(post)
    db_session.commit()

    due_posts = get_due_posts_query(db_session, now_utc).all()
    due_ids = [p.id for p in due_posts]
    assert post.id in due_ids


# ==============================================================================
# TEST 3 — Draft Should NOT Be Selected
# ==============================================================================
def test_3_draft_not_selected(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_draft_scan@test.com", "Draft User")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Draft post with past timestamp",
        status=PostStatus.draft.value,
        scheduled_at=now_utc - timedelta(minutes=10),
    )
    db_session.add(post)
    db_session.commit()

    due_posts = get_due_posts_query(db_session, now_utc).all()
    due_ids = [p.id for p in due_posts]
    assert post.id not in due_ids


# ==============================================================================
# TEST 4 — Published Post Should NOT Be Selected
# ==============================================================================
def test_4_published_post_not_selected(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_pub_scan@test.com", "Pub User")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Already published post",
        status=PostStatus.published.value,
        scheduled_at=now_utc - timedelta(minutes=10),
        published_at=now_utc - timedelta(minutes=10),
    )
    db_session.add(post)
    db_session.commit()

    due_posts = get_due_posts_query(db_session, now_utc).all()
    due_ids = [p.id for p in due_posts]
    assert post.id not in due_ids


# ==============================================================================
# TEST 5 — Due Post Is Atomically Claimed (SCHEDULED -> PUBLISHING)
# ==============================================================================
def test_5_due_post_atomically_claimed(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_claim@test.com", "Claim User")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post to claim atomically",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=2),
    )
    db_session.add(post)
    db_session.commit()

    # Claiming transitions status to 'publishing'
    claimed = claim_post_for_publishing(db_session, post.id)
    assert claimed is True

    db_session.refresh(post)
    assert post.status == PostStatus.publishing.value


# ==============================================================================
# TEST 6 & 7 — Publishing Service Called & Status Updates to PUBLISHED
# ==============================================================================
def test_6_7_successful_automated_publish(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_auto_pub@test.com", "Auto User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Auto LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Automated publish through Celery worker!",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:auto_777888"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = process_due_post(db_session, post.id)

    assert res["claimed"] is True
    assert res["status"] == PostStatus.published.value

    db_session.refresh(post)
    assert post.status == PostStatus.published.value
    assert post.published_at is not None
    assert len(post.publish_results) == 1
    assert post.publish_results[0].status == "published"
    assert post.publish_results[0].platform_post_id == "urn:li:share:auto_777888"


# ==============================================================================
# TEST 8 — Publishing Failure Changes Status to FAILED
# ==============================================================================
def test_8_failed_automated_publish(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_auto_fail@test.com", "Fail Auto User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Auto LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Automated publish that encounters platform error",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    mock_resp = httpx.Response(
        500,
        json={"message": "LinkedIn internal server error"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = process_due_post(db_session, post.id)

    assert res["claimed"] is True
    assert res["status"] == PostStatus.failed.value

    db_session.refresh(post)
    assert post.status == PostStatus.failed.value
    assert len(post.publish_results) == 1
    assert post.publish_results[0].status == "failed"


# ==============================================================================
# TEST 9 — Multi-Platform Publishing Works Through Phase 5 Service
# ==============================================================================
def test_9_multi_platform_automated_publishing(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_multi_auto@test.com", "Multi Auto User")
    li_acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Auto LinkedIn")
    x_acc = _seed_account(db_session, user_id, SocialPlatform.x, "Auto X")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Cross-platform automated broadcast",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=li_acc.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=x_acc.id))
    db_session.commit()

    async def mock_post_call(url, *args, **kwargs):
        if "linkedin" in str(url):
            return httpx.Response(
                201,
                json={"id": "urn:li:share:multi_999"},
                request=httpx.Request("POST", str(url)),
            )
        else:
            return httpx.Response(
                201,
                json={"data": {"id": "x_tweet_888"}},
                request=httpx.Request("POST", str(url)),
            )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, side_effect=mock_post_call):
        res = process_due_post(db_session, post.id)

    assert res["claimed"] is True
    assert res["status"] == PostStatus.published.value

    db_session.refresh(post)
    assert len(post.publish_results) == 2
    assert all(pr.status == "published" for pr in post.publish_results)


# ==============================================================================
# TEST 10 — Recurring Post Generated Occurrence Is Eligible for Auto-Publishing
# ==============================================================================
def test_10_recurring_post_occurrence_eligible(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_rec_auto@test.com", "Rec Auto User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Rec LinkedIn")
    now_utc = datetime.now(timezone.utc)

    rule = RecurringRule(
        user_id=user_id,
        content="Daily inspirational recurring quote",
        frequency=RecurrenceFrequency.daily.value,
        start_at=now_utc - timedelta(days=2),
        end_at=now_utc + timedelta(days=5),
        is_active=True,
    )
    db_session.add(rule)
    db_session.flush()

    # Occurrence generated for earlier today that is now due
    occurrence = Post(
        user_id=user_id,
        content=rule.content,
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=10),
        recurring_rule_id=rule.id,
    )
    db_session.add(occurrence)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=occurrence.id, social_account_id=acc.id))
    db_session.commit()

    due_posts = get_due_posts_query(db_session, now_utc).all()
    assert occurrence.id in [p.id for p in due_posts]

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:rec_123"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = process_due_post(db_session, occurrence.id)

    assert res["status"] == PostStatus.published.value
    db_session.refresh(occurrence)
    assert occurrence.status == PostStatus.published.value


# ==============================================================================
# TEST 11 — Ownership and User Isolation Remain Intact
# ==============================================================================
def test_11_ownership_isolation_preserved(client, db_session):
    user_a, _, headers_a = _register_and_login(client, "user_a_sec@test.com", "User A")
    user_b, _, headers_b = _register_and_login(client, "user_b_sec@test.com", "User B")
    acc_a = _seed_account(db_session, user_a, SocialPlatform.linkedin, "User A LI")
    now_utc = datetime.now(timezone.utc)

    post_a = Post(
        user_id=user_a,
        content="User A content",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=5),
    )
    db_session.add(post_a)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post_a.id, social_account_id=acc_a.id))
    db_session.commit()

    # User B cannot publish or access User A's post via API
    res = client.post(f"/api/v1/posts/{post_a.id}/publish", headers=headers_b)
    assert res.status_code == 403


# ==============================================================================
# TEST 12 (MANDATORY) — Duplicate Publish Protection (Worker A claims, Worker B skips)
# ==============================================================================
def test_12_duplicate_publish_prevention(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_dup_test@test.com", "Dup User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Dup LI")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post targeted by two concurrent workers",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=2),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:first_worker_win"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        # Worker A processes the post
        res_worker_a = process_due_post(db_session, post.id)

        # Worker B sees the exact same post simultaneously
        res_worker_b = process_due_post(db_session, post.id)

    # Worker A claimed and published
    assert res_worker_a["claimed"] is True
    assert res_worker_a["status"] == PostStatus.published.value

    # Worker B was rejected from claiming because status is no longer SCHEDULED
    assert res_worker_b["claimed"] is False
    assert res_worker_b["status"] == "skipped"

    db_session.refresh(post)
    assert post.status == PostStatus.published.value
    # Exactly one publish result was created
    assert len(post.publish_results) == 1
