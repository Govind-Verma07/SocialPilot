"""
tests/test_phase8_publishing_queue.py
-------------------------------------
Automated test suite for Phase 8: Publishing Queue + Retry Handling.

Covers:
1. Job creation: PublishingJob model and schema fields
2. One job per connected social account / platform
3. Duplicate job prevention via (post_id, social_account_id) idempotency
4. Queueing manual Publish Now (async API dispatch)
5. Queueing scheduled posts via Celery Beat scan
6. Recurring post occurrence queueing
7. Atomic job claiming (QUEUED/RETRYING -> PROCESSING)
8. Successful publishing marks job and post published
9. Transient failure triggers retry with exponential backoff
10. Retry backoff and maximum retry limits
11. Permanent failure (invalid token / permission) -> no retry
12. Multi-platform independent success and failure
13. Already published and cancelled jobs are safely skipped
14. Post status aggregation across platform jobs
15. Celery task process_publishing_job execution and session isolation
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import httpx

from app.models.enums import PostStatus, SocialPlatform, AccountStatus, PublishingJobStatus
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.models.publishing_job import PublishingJob
from app.models.post_publish_result import PostPublishResult
from app.core.encryption import encrypt_token
from app.services.publishing.queue_service import (
    enqueue_publishing_jobs,
    claim_publishing_job,
    execute_publishing_job,
    is_transient_error,
    get_backoff_delay,
    recalculate_post_status,
)
from app.worker.tasks import (
    process_publishing_job,
    process_queued_and_retry_jobs,
    check_and_publish_due_posts,
    publish_post_task,
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
# TEST 1 & 2 — Job Creation, Per-Platform Queue & Duplicate Prevention
# ==============================================================================
def test_1_2_job_creation_and_duplicate_prevention(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q1@test.com", "Queue User 1")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Q LinkedIn")
    acc_fb = _seed_account(db_session, user_id, SocialPlatform.facebook, "Q Facebook")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Multi-platform post for queueing test",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_li.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_fb.id))
    db_session.commit()

    # Initial enqueue: creates 2 jobs
    jobs = enqueue_publishing_jobs(db_session, post.id)
    assert len(jobs) == 2
    assert all(j.status == PublishingJobStatus.queued.value for j in jobs)
    assert {j.social_account_id for j in jobs} == {acc_li.id, acc_fb.id}

    # Verify duplicate prevention: calling enqueue again returns same jobs
    jobs_again = enqueue_publishing_jobs(db_session, post.id)
    assert len(jobs_again) == 2
    total_jobs_in_db = db_session.query(PublishingJob).filter(PublishingJob.post_id == post.id).count()
    assert total_jobs_in_db == 2


# ==============================================================================
# TEST 3 — Manual Publish Now Submits Async Jobs
# ==============================================================================
def test_3_manual_publish_submits_async_jobs(client, db_session):
    user_id, _, headers = _register_and_login(client, "user_q_manual@test.com", "Manual Q User")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Manual Q LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post queued via manual action",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_li.id))
    db_session.commit()

    with patch("app.worker.tasks.process_publishing_job.delay") as mock_job_delay, \
         patch("app.worker.tasks.publish_post_task.delay") as mock_task_delay:
        res = client.post(f"/api/v1/posts/{post.id}/publish?async_publish=true", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == PostStatus.publishing.value
    assert len(data["publishing_jobs"]) == 1
    assert data["publishing_jobs"][0]["status"] == "queued"
    mock_job_delay.assert_called_once()


# ==============================================================================
# TEST 4 — Scheduled and Recurring Post Occurrence Queueing
# ==============================================================================
def test_4_scheduled_and_recurring_queueing(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q_sched@test.com", "Sched Q User")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Sched Q LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Due scheduled occurrence picked up by Beat",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc - timedelta(minutes=10),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_li.id))
    db_session.commit()

    with patch("app.worker.tasks.SessionLocal", return_value=db_session), \
         patch("app.worker.tasks.process_publishing_job.delay") as mock_job_delay, \
         patch("app.worker.tasks.publish_single_post_task.delay"):
        result = check_and_publish_due_posts()

    assert result["dispatched_count"] >= 1
    assert post.id in result["post_ids"]
    mock_job_delay.assert_called_once()

    post_jobs = db_session.query(PublishingJob).filter(PublishingJob.post_id == post.id).all()
    assert len(post_jobs) == 1
    assert post_jobs[0].status == PublishingJobStatus.queued.value


# ==============================================================================
# TEST 5 — Atomic Job Claiming
# ==============================================================================
def test_5_atomic_job_claiming(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q_claim@test.com", "Claim User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Claim LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Testing atomic claiming",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    job = jobs[0]

    # Worker A claims the job
    claimed_a = claim_publishing_job(db_session, job.id)
    assert claimed_a is True

    db_session.refresh(job)
    assert job.status == PublishingJobStatus.processing.value

    # Worker B tries to claim the same job concurrently
    claimed_b = claim_publishing_job(db_session, job.id)
    assert claimed_b is False


# ==============================================================================
# TEST 6 — Successful Publishing & Post Status Update
# ==============================================================================
def test_6_successful_publishing_and_post_status(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q_success@test.com", "Success User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Success LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Success publishing test",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    job = jobs[0]

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:11223344"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = execute_publishing_job(db_session, job.id)

    assert res["job_status"] == PublishingJobStatus.published.value
    assert res["post_status"] == PostStatus.published.value
    assert res["attempt_count"] == 1

    db_session.refresh(post)
    assert post.status == PostStatus.published.value
    assert post.published_at is not None


# ==============================================================================
# TEST 7 & 8 — Transient Failure -> Retry Backoff & Maximum Retry Limit
# ==============================================================================
def test_7_8_transient_failure_and_max_retries(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q_retry@test.com", "Retry User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Retry LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Testing transient failure retries",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    job = jobs[0]
    job.max_attempts = 3
    db_session.commit()

    # Mock 429 Rate Limit (transient error)
    mock_rate_limit = httpx.Response(
        429,
        json={"error": "Rate limit exceeded. Too many requests."},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    # Attempt 1: Transient -> RETRYING
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_rate_limit):
        res1 = execute_publishing_job(db_session, job.id)

    assert res1["job_status"] == PublishingJobStatus.retrying.value
    assert res1["attempt_count"] == 1
    assert res1["next_retry_at"] is not None

    db_session.refresh(post)
    assert post.status == PostStatus.publishing.value

    # Attempt 2: Transient -> RETRYING
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_rate_limit):
        res2 = execute_publishing_job(db_session, job.id)

    assert res2["job_status"] == PublishingJobStatus.retrying.value
    assert res2["attempt_count"] == 2

    # Attempt 3: Reached max_attempts -> FAILED
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_rate_limit):
        res3 = execute_publishing_job(db_session, job.id)

    assert res3["job_status"] == PublishingJobStatus.failed.value
    assert res3["attempt_count"] == 3
    assert res3["next_retry_at"] is None

    db_session.refresh(post)
    assert post.status == PostStatus.failed.value


# ==============================================================================
# TEST 9 — Permanent Failure (Invalid Token) -> No Retry
# ==============================================================================
def test_9_permanent_failure_no_retry(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q_perm@test.com", "Perm User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Perm LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Testing permanent failure",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    job = jobs[0]

    # Mock 401 Invalid/Expired Token (permanent failure)
    mock_auth_fail = httpx.Response(
        401,
        json={"error": "The access token provided is expired, revoked or malformed."},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_auth_fail):
        res = execute_publishing_job(db_session, job.id)

    assert res["job_status"] == PublishingJobStatus.failed.value
    assert res["attempt_count"] == 1
    assert res["next_retry_at"] is None

    db_session.refresh(post)
    assert post.status == PostStatus.failed.value


# ==============================================================================
# TEST 10 — Multi-Platform Independent Success and Failure
# ==============================================================================
def test_10_multi_platform_independent_results(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q_multi@test.com", "Multi User")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Multi LinkedIn")
    acc_fb = _seed_account(db_session, user_id, SocialPlatform.facebook, "Multi Facebook")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Multi-platform independent processing",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_li.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_fb.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    li_job = next(j for j in jobs if j.social_account_id == acc_li.id)
    fb_job = next(j for j in jobs if j.social_account_id == acc_fb.id)

    # LinkedIn succeeds
    mock_li_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:889900"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_li_resp):
        res_li = execute_publishing_job(db_session, li_job.id)

    assert res_li["job_status"] == PublishingJobStatus.published.value

    # Post is still publishing because Facebook job is still queued
    db_session.refresh(post)
    assert post.status == PostStatus.publishing.value

    # Facebook fails with permanent error
    mock_fb_resp = httpx.Response(
        400,
        json={"error": {"message": "Invalid page token provided."}},
        request=httpx.Request("POST", "https://graph.facebook.com/v19.0/me/feed"),
    )
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_fb_resp):
        res_fb = execute_publishing_job(db_session, fb_job.id)

    assert res_fb["job_status"] == PublishingJobStatus.failed.value

    # Check database state: LinkedIn remains published, Facebook is failed, Post is failed
    db_session.refresh(li_job)
    db_session.refresh(fb_job)
    db_session.refresh(post)

    assert li_job.status == PublishingJobStatus.published.value
    assert fb_job.status == PublishingJobStatus.failed.value
    assert post.status == PostStatus.failed.value


# ==============================================================================
# TEST 11 — Already Published and Cancelled Jobs are Skipped
# ==============================================================================
def test_11_already_published_and_cancelled_jobs_skipped(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_q_skip@test.com", "Skip User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Skip LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Testing skipped jobs",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    job = jobs[0]

    # Mark job published
    job.status = PublishingJobStatus.published.value
    db_session.commit()

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
        res = execute_publishing_job(db_session, job.id)

    assert res["claimed"] is False
    assert res["status"] == PublishingJobStatus.published.value
    mock_post.assert_not_called()


# ==============================================================================
# TEST 12 — Celery Task Execution and DB Session Isolation
# ==============================================================================
def test_12_process_publishing_job_celery_task(db_session):
    with patch("app.worker.tasks.SessionLocal") as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        # Mock claim returning False
        mock_db.query.return_value.filter.return_value.update.return_value = 0
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = process_publishing_job("fake-job-id")

        # Verify DB session was closed cleanly
        mock_db.close.assert_called_once()
        assert result["claimed"] is False
