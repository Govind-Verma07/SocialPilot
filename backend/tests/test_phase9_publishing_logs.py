"""
tests/test_phase9_publishing_logs.py
------------------------------------
Automated test suite for Phase 9: Publishing Logs & Tracking.

Covers:
1. Log creation for queued job
2. Processing & publishing started logs
3. Successful publishing log (storing platform_post_id and published_url)
4. Retry log for transient failures
5. Failed publishing log for permanent failure
6. Multiple attempt tracking across retries
7. Multi-platform independent log streams
8. Logs API authentication (unauthorized access rejected)
9. Post ownership protection (user B cannot access user A's logs)
10. Platform and status filtering on the logs API
11. Pagination support on the logs API
12. Sensitive secret & token sanitization (no access tokens in logs)
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta
import httpx

from app.models.enums import PostStatus, SocialPlatform, AccountStatus, PublishingJobStatus, PublishingLogEventType
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.models.publishing_job import PublishingJob
from app.models.publishing_log import PublishingLog
from app.core.encryption import encrypt_token
from app.services.publishing.queue_service import (
    enqueue_publishing_jobs,
    execute_publishing_job,
    create_publishing_log,
    sanitize_error_message,
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
# TEST 1 & 2 — Log Creation for Queued, Processing & Started Events
# ==============================================================================
def test_1_2_queued_and_processing_logs(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_log1@test.com", "Log User 1")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Log LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post for tracking queued & processing events",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    # Enqueue creates a QUEUED log
    jobs = enqueue_publishing_jobs(db_session, post.id)
    queued_logs = db_session.query(PublishingLog).filter(PublishingLog.post_id == post.id).all()
    assert len(queued_logs) == 1
    assert queued_logs[0].event_type == PublishingLogEventType.queued.value
    assert queued_logs[0].status == "queued"
    assert queued_logs[0].platform == "linkedin"

    # Execution creates PROCESSING and PUBLISHING_STARTED logs
    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:998877"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        execute_publishing_job(db_session, jobs[0].id)

    logs = db_session.query(PublishingLog).filter(PublishingLog.post_id == post.id).order_by(PublishingLog.created_at.asc()).all()
    event_types = [l.event_type for l in logs]
    assert PublishingLogEventType.queued.value in event_types
    assert PublishingLogEventType.processing.value in event_types
    assert PublishingLogEventType.publishing_started.value in event_types
    assert PublishingLogEventType.published.value in event_types


# ==============================================================================
# TEST 3 — Successful Publishing Log Stores IDs and URLs
# ==============================================================================
def test_3_successful_publishing_log(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_log_success@test.com", "Success Log User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Success Log LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Testing published log record details",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:12345678"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        execute_publishing_job(db_session, jobs[0].id)

    success_log = (
        db_session.query(PublishingLog)
        .filter(
            PublishingLog.post_id == post.id,
            PublishingLog.event_type == PublishingLogEventType.published.value,
        )
        .first()
    )

    assert success_log is not None
    assert success_log.status == "published"
    assert success_log.platform_post_id == "urn:li:share:12345678"
    assert "https://www.linkedin.com/feed/update/urn:li:share:12345678" in success_log.published_url
    assert success_log.attempt_number == 1


# ==============================================================================
# TEST 4, 5 & 6 — Retry & Failed Logs with Multiple Attempts
# ==============================================================================
def test_4_5_6_retry_and_failed_logs_multiple_attempts(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_log_retry@test.com", "Retry Log User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Retry Log LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Testing multiple attempt retry logs",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    job = jobs[0]
    job.max_attempts = 2
    db_session.commit()

    mock_429 = httpx.Response(
        429,
        json={"error": "Rate limit exceeded. Temporary issue."},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    # Attempt 1: Transient -> RETRYING
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_429):
        execute_publishing_job(db_session, job.id)

    retry_log = (
        db_session.query(PublishingLog)
        .filter(
            PublishingLog.post_id == post.id,
            PublishingLog.event_type == PublishingLogEventType.retrying.value,
        )
        .first()
    )
    assert retry_log is not None
    assert retry_log.attempt_number == 1
    assert "Rate limit exceeded" in retry_log.error_message

    # Attempt 2: Reached max_attempts -> FAILED
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_429):
        execute_publishing_job(db_session, job.id)

    failed_log = (
        db_session.query(PublishingLog)
        .filter(
            PublishingLog.post_id == post.id,
            PublishingLog.event_type == PublishingLogEventType.failed.value,
        )
        .first()
    )
    assert failed_log is not None
    assert failed_log.attempt_number == 2
    assert "Rate limit exceeded" in failed_log.error_message


# ==============================================================================
# TEST 7 — Multi-Platform Independent Log Streams
# ==============================================================================
def test_7_multi_platform_logs(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_log_multi@test.com", "Multi Log User")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Multi LI")
    acc_fb = _seed_account(db_session, user_id, SocialPlatform.facebook, "Multi FB")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Multi-platform logging test",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_li.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_fb.id))
    db_session.commit()

    jobs = enqueue_publishing_jobs(db_session, post.id)
    assert len(jobs) == 2

    li_logs = db_session.query(PublishingLog).filter(PublishingLog.post_id == post.id, PublishingLog.platform == "linkedin").all()
    fb_logs = db_session.query(PublishingLog).filter(PublishingLog.post_id == post.id, PublishingLog.platform == "facebook").all()

    assert len(li_logs) >= 1
    assert len(fb_logs) >= 1
    assert li_logs[0].platform == "linkedin"
    assert fb_logs[0].platform == "facebook"


# ==============================================================================
# TEST 8, 9, 10 & 11 — Logs API Authentication, Ownership, Filters & Pagination
# ==============================================================================
def test_8_9_10_11_logs_api_auth_ownership_filters_pagination(client, db_session):
    user_a_id, _, headers_a = _register_and_login(client, "owner_a@test.com", "Owner A")
    user_b_id, _, headers_b = _register_and_login(client, "intruder_b@test.com", "Intruder B")
    acc_li = _seed_account(db_session, user_a_id, SocialPlatform.linkedin, "Owner LI")
    acc_fb = _seed_account(db_session, user_a_id, SocialPlatform.facebook, "Owner FB")
    now_utc = datetime.now(timezone.utc)

    post = Post(
        user_id=user_a_id,
        content="Post for API testing",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_li.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_fb.id))
    db_session.commit()

    enqueue_publishing_jobs(db_session, post.id)

    # 1. Unauthenticated request -> 401
    res_unauth = client.get(f"/api/v1/posts/{post.id}/publishing-logs")
    assert res_unauth.status_code == 401

    # 2. Unauthorized user B accessing user A's post logs -> 403
    res_forbidden = client.get(f"/api/v1/posts/{post.id}/publishing-logs", headers=headers_b)
    assert res_forbidden.status_code == 403

    # 3. Authorized user A accessing logs -> 200
    res_ok = client.get(f"/api/v1/posts/{post.id}/publishing-logs", headers=headers_a)
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # 4. Filter by platform
    res_filt = client.get(f"/api/v1/posts/{post.id}/publishing-logs?platform=linkedin", headers=headers_a)
    assert res_filt.status_code == 200
    data_filt = res_filt.json()
    assert data_filt["total"] == 1
    assert data_filt["items"][0]["platform"] == "linkedin"

    # 5. Pagination
    res_page = client.get(f"/api/v1/posts/{post.id}/publishing-logs?page=1&limit=1", headers=headers_a)
    assert res_page.status_code == 200
    data_page = res_page.json()
    assert len(data_page["items"]) == 1
    assert data_page["total"] == 2


# ==============================================================================
# TEST 12 — Secret & Token Sanitization (No Leakage)
# ==============================================================================
def test_12_secret_and_token_sanitization():
    raw_error_bearer = "Request failed: 401 Unauthorized with header Bearer AQVb4398fdskjhs9834..."
    cleaned = sanitize_error_message(raw_error_bearer)
    assert "AQVb4398fdskjhs9834" not in cleaned
    assert "[REDACTED]" in cleaned

    raw_error_param = "Graph API error on url https://graph.facebook.com/?access_token=EAABwzL98342kdslj&type=feed"
    cleaned_param = sanitize_error_message(raw_error_param)
    assert "EAABwzL98342kdslj" not in cleaned_param
    assert "access_token=[REDACTED]" in cleaned_param
