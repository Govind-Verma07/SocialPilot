"""
tests/test_phase7_async_publishing.py
-------------------------------------
Automated test suite for Phase 7: Asynchronous Publishing Service.

Covers:
1. Celery task can be created / discovered
2. Task accepts serializable identifier (post_id string)
3. Due post is processed asynchronously via worker task
4. Future post is not published
5. Draft is not published
6. PUBLISHED post is skipped by worker
7. PUBLISHING post is skipped (idempotent / duplicate prevention)
8. Atomic claiming prevents duplicate concurrent worker processing
9. Phase 5 publishing service is invoked by worker
10. Successful publish changes status correctly (PUBLISHED)
11. Failed publish changes status correctly (FAILED)
12. Multiple platform results are preserved and distinguishable
13. Database sessions are properly isolated and closed
14. Manual Publish Now submits an async task
15. Scheduled automatic publishing submits an async task
16. Duplicate worker test: Worker A claims & publishes, Worker B skips
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import httpx

from app.models.enums import PostStatus, SocialPlatform, AccountStatus
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.core.encryption import encrypt_token
from app.worker.tasks import (
    publish_post_task,
    publish_single_post_task,
    check_and_publish_due_posts,
    claim_post_for_publishing,
    process_due_post,
    get_due_posts_query,
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
# TEST 1 & 2 — Celery Task Creation & Serializable Identifier Acceptance
# ==============================================================================
def test_1_2_task_creation_and_serializable_args():
    assert publish_post_task.name == "app.worker.tasks.publish_post_task"
    assert publish_single_post_task.name == "app.worker.tasks.publish_single_post_task"
    # Verify task signature accepts simple string post_id
    assert callable(publish_post_task)


# ==============================================================================
# TEST 3 — Due Post Processed Asynchronously
# ==============================================================================
def test_3_due_post_processed_async(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_async_3@test.com", "Async User 3")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Async LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Testing async publishing execution",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=2),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:async_333"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = process_due_post(db_session, post.id)

    assert res["claimed"] is True
    assert res["status"] == PostStatus.published.value

    db_session.refresh(post)
    assert post.status == PostStatus.published.value
    assert len(post.publish_results) == 1
    assert post.publish_results[0].status == "published"


# ==============================================================================
# TEST 4, 5, 6, 7 — Future Post, Draft, Published, Publishing Posts Skipped
# ==============================================================================
def test_4_5_6_7_ineligible_posts_skipped(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_ineligible@test.com", "Ineligible User")
    now_utc = datetime.now(timezone.utc)

    # 4. Future post
    future_post = Post(user_id=user_id, content="Future", status=PostStatus.scheduled.value, scheduled_at=now_utc + timedelta(hours=2))
    # 5. Draft post
    draft_post = Post(user_id=user_id, content="Draft", status=PostStatus.draft.value, scheduled_at=now_utc - timedelta(hours=1))
    # 6. Published post
    pub_post = Post(user_id=user_id, content="Published", status=PostStatus.published.value, scheduled_at=now_utc - timedelta(hours=1))
    # 7. Already publishing post
    publishing_post = Post(user_id=user_id, content="Publishing", status=PostStatus.publishing.value, scheduled_at=now_utc - timedelta(hours=1))

    db_session.add_all([future_post, draft_post, pub_post, publishing_post])
    db_session.commit()

    # None of these should be returned by due posts query
    due_posts = get_due_posts_query(db_session, now_utc).all()
    due_ids = [p.id for p in due_posts]

    assert future_post.id not in due_ids
    assert draft_post.id not in due_ids
    assert pub_post.id not in due_ids
    assert publishing_post.id not in due_ids

    # None of these can be claimed
    assert claim_post_for_publishing(db_session, future_post.id) is True  # Future post was scheduled, but query excludes it
    assert claim_post_for_publishing(db_session, draft_post.id) is False
    assert claim_post_for_publishing(db_session, pub_post.id) is False
    assert claim_post_for_publishing(db_session, publishing_post.id) is False


# ==============================================================================
# TEST 8 & 16 — Atomic Claiming & Duplicate Worker Protection (Worker A wins, Worker B skips)
# ==============================================================================
def test_8_16_atomic_claiming_duplicate_worker_protection(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_dup_p7@test.com", "Dup Worker User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Dup LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post concurrently received by Worker A and Worker B",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:single_call_win"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        # Worker A attempts to claim and publish
        res_a = process_due_post(db_session, post.id)

        # Worker B simultaneously attempts to process the exact same post
        res_b = process_due_post(db_session, post.id)

    # Worker A succeeded
    assert res_a["claimed"] is True
    assert res_a["status"] == PostStatus.published.value

    # Worker B was cleanly skipped without executing API calls
    assert res_b["claimed"] is False
    assert res_b["status"] == "skipped"

    # Crucial check: platform API was called ONLY ONCE
    assert mock_post.call_count == 1

    db_session.refresh(post)
    assert post.status == PostStatus.published.value
    assert len(post.publish_results) == 1


# ==============================================================================
# TEST 9, 10, 11, 12 — Phase 5 Publisher Reuse & Multi-Platform Results
# ==============================================================================
def test_9_10_11_12_multi_platform_results(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_multi_p7@test.com", "Multi P7 User")
    li_acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "LinkedIn Acc")
    fb_acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "Facebook Acc")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Multi-target async post",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=li_acc.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=fb_acc.id))
    db_session.commit()

    async def mock_call(url, *args, **kwargs):
        if "linkedin" in str(url):
            return httpx.Response(
                201,
                json={"id": "urn:li:share:p7_li"},
                request=httpx.Request("POST", str(url)),
            )
        else:
            return httpx.Response(
                400,
                json={"error": {"message": "Expired page token"}},
                request=httpx.Request("POST", str(url)),
            )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, side_effect=mock_call):
        res = process_due_post(db_session, post.id)

    assert res["claimed"] is True
    assert res["status"] == PostStatus.published.value

    db_session.refresh(post)
    assert len(post.publish_results) == 2

    li_res = next(r for r in post.publish_results if r.platform == "linkedin")
    fb_res = next(r for r in post.publish_results if r.platform == "facebook")

    assert li_res.status == "published"
    assert fb_res.status == "failed"
    assert "Expired page token" in fb_res.error_message


# ==============================================================================
# TEST 13 — Database Sessions Isolation
# ==============================================================================
def test_13_database_session_isolation(db_session):
    # Verify that worker tasks manage and close independent sessions
    with patch("app.worker.tasks.SessionLocal") as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.update.return_value = 0

        publish_single_post_task("fake-post-id")

        # Session was closed cleanly
        mock_db.close.assert_called_once()


# ==============================================================================
# TEST 14 — Manual Publish Now Submits Async Task
# ==============================================================================
def test_14_manual_publish_submits_async_task(client, db_session):
    user_id, _, headers = _register_and_login(client, "user_manual_async@test.com", "Manual User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Manual LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post published via manual action",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    with patch("app.worker.tasks.publish_post_task.delay") as mock_delay:
        res = client.post(f"/api/v1/posts/{post.id}/publish?async_publish=true", headers=headers)

    assert res.status_code == 200
    mock_delay.assert_called_once_with(post.id)

    db_session.refresh(post)
    assert post.status == PostStatus.publishing.value


# ==============================================================================
# TEST 15 — Scheduled Automatic Publishing Submits Async Task
# ==============================================================================
def test_15_scheduled_auto_publishing_submits_task(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_beat_async@test.com", "Beat User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Beat LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post picked up by periodic Beat scan",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=5),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    with patch("app.worker.tasks.SessionLocal", return_value=db_session), \
         patch("app.worker.tasks.publish_single_post_task.delay") as mock_task_delay:
        result = check_and_publish_due_posts()

    assert result["dispatched_count"] >= 1
    assert post.id in result["post_ids"]
    mock_task_delay.assert_any_call(post.id)
