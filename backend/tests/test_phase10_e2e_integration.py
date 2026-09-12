"""
tests/test_phase10_e2e_integration.py
-------------------------------------
Automated End-to-End Integration Test Suite for Phase 10: Final System Verification.

Validates the full lifecycle:
User Auth -> Connect Accounts -> Create Draft -> Schedule Post -> Calendar Retrieval ->
Queueing -> Asynchronous Publishing -> Platform Execution -> Status Transitions ->
Retry Handling -> Event Logs & Timeline -> Security & Sanitization.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
import httpx

from app.models.enums import (
    PostStatus,
    SocialPlatform,
    AccountStatus,
    PublishingJobStatus,
    PublishingLogEventType,
    RecurrenceFrequency,
)
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.models.publishing_job import PublishingJob
from app.models.publishing_log import PublishingLog
from app.models.recurring_rule import RecurringRule
from app.core.encryption import encrypt_token
from app.services.publishing.queue_service import (
    enqueue_publishing_jobs,
    claim_publishing_job,
    execute_publishing_job,
    sanitize_error_message,
)
from app.worker.tasks import (
    process_publishing_job,
    process_queued_and_retry_jobs,
    check_and_publish_due_posts,
    publish_post_task,
)


def _register_and_login(client, email: str, name: str = "E2E User") -> tuple[str, str, dict]:
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


def _seed_account(db_session, user_id: str, platform: SocialPlatform, name: str, token: str = "mock-e2e-token") -> SocialAccount:
    """Helper to create a connected social account in DB."""
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_e2e_{user_id[:6]}",
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
# TEST 1 — Complete End-to-End Publishing Workflow
# ==============================================================================
def test_1_full_e2e_publishing_lifecycle(client, db_session):
    # 1. Register & Login
    user_id, token, headers = _register_and_login(client, "e2e_full@test.com", "E2E Full User")
    acc_li = _seed_account(db_session, user_id, SocialPlatform.linkedin, "E2E LinkedIn")
    acc_fb = _seed_account(db_session, user_id, SocialPlatform.facebook, "E2E Facebook")
    now_utc = datetime.now(timezone.utc)

    # 2. Create Draft Post
    res_draft = client.post(
        "/api/v1/posts",
        json={
            "content": "Initial draft content for E2E verification",
            "status": "draft",
            "post_type": "text",
        },
        headers=headers,
    )
    assert res_draft.status_code == 201
    post_data = res_draft.json()
    post_id = post_data["id"]
    assert post_data["status"] == "draft"

    # 3. Update Draft to SCHEDULED
    future_time = (now_utc + timedelta(days=2)).isoformat()
    res_sched = client.put(
        f"/api/v1/posts/{post_id}",
        json={
            "content": "Final scheduled content for E2E multi-platform publish 🚀",
            "status": "scheduled",
            "scheduled_at": future_time,
            "social_account_ids": [acc_li.id, acc_fb.id],
        },
        headers=headers,
    )
    assert res_sched.status_code == 200
    assert res_sched.json()["status"] == "scheduled"
    assert len(res_sched.json()["social_accounts"]) == 2

    # 4. Trigger Asynchronous Publish Now
    with patch("app.worker.tasks.process_publishing_job.delay") as mock_job_delay, \
         patch("app.worker.tasks.publish_post_task.delay"):
        res_pub = client.post(f"/api/v1/posts/{post_id}/publish?async_publish=true", headers=headers)

    assert res_pub.status_code == 200
    pub_data = res_pub.json()
    assert pub_data["status"] == PostStatus.publishing.value
    assert len(pub_data["publishing_jobs"]) == 2
    assert mock_job_delay.call_count == 2

    # 5. Process LinkedIn Job (Success)
    li_job = next(j for j in pub_data["publishing_jobs"] if j["social_account_id"] == acc_li.id)
    mock_li = httpx.Response(
        201,
        json={"id": "urn:li:share:987654"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_li):
        res_li = execute_publishing_job(db_session, li_job["id"])

    assert res_li["job_status"] == PublishingJobStatus.published.value

    # 6. Process Facebook Job (Transient 429 Error -> Retrying)
    fb_job = next(j for j in pub_data["publishing_jobs"] if j["social_account_id"] == acc_fb.id)
    mock_fb_429 = httpx.Response(
        429,
        json={"error": {"message": "Rate limit exceeded. Try again in 60s."}},
        request=httpx.Request("POST", "https://graph.facebook.com/v19.0/me/feed"),
    )
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_fb_429):
        res_fb = execute_publishing_job(db_session, fb_job["id"])

    assert res_fb["job_status"] == PublishingJobStatus.retrying.value
    assert res_fb["attempt_count"] == 1
    assert res_fb["next_retry_at"] is not None

    # Post remains in publishing status because one platform is retrying
    post = db_session.query(Post).filter(Post.id == post_id).first()
    assert post.status == PostStatus.publishing.value

    # 7. Check Publishing Timeline & History API
    res_logs = client.get(f"/api/v1/posts/{post_id}/publishing-logs", headers=headers)
    assert res_logs.status_code == 200
    log_data = res_logs.json()
    assert log_data["total"] >= 4
    event_types = [l["event_type"] for l in log_data["items"]]
    assert "QUEUED" in event_types
    assert "PROCESSING" in event_types
    assert "PUBLISHED" in event_types
    assert "RETRYING" in event_types


# ==============================================================================
# TEST 2 — Security & Ownership Enforcement
# ==============================================================================
def test_2_security_ownership_isolation(client, db_session):
    user_a_id, _, headers_a = _register_and_login(client, "user_sec_a@test.com", "Security A")
    user_b_id, _, headers_b = _register_and_login(client, "user_sec_b@test.com", "Security B")
    acc_a = _seed_account(db_session, user_a_id, SocialPlatform.linkedin, "User A LinkedIn")
    now_utc = datetime.now(timezone.utc)

    post_a = Post(
        user_id=user_a_id,
        content="Secret post owned by User A",
        status=PostStatus.scheduled.value,
        scheduled_at=now_utc + timedelta(days=1),
    )
    db_session.add(post_a)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post_a.id, social_account_id=acc_a.id))
    db_session.commit()

    # User B cannot publish User A's post -> 403
    res_pub = client.post(f"/api/v1/posts/{post_a.id}/publish", headers=headers_b)
    assert res_pub.status_code == 403

    # User B cannot view User A's publishing logs -> 403
    res_logs = client.get(f"/api/v1/posts/{post_a.id}/publishing-logs", headers=headers_b)
    assert res_logs.status_code == 403

    # User B cannot attach User A's social account -> 400 or 403
    res_create = client.post(
        "/api/v1/posts",
        json={
            "content": "Malicious post attempting to hijack User A's account",
            "status": "scheduled",
            "scheduled_at": (now_utc + timedelta(days=1)).isoformat(),
            "social_account_ids": [acc_a.id],
        },
        headers=headers_b,
    )
    assert res_create.status_code in (400, 403)


# ==============================================================================
# TEST 3 — Sanitization & No Sensitive Secret Leakage
# ==============================================================================
def test_3_secret_sanitization():
    raw_message = "Failed to connect: Bearer secret_live_token_123456 with access_token=ghp_999988887777"
    cleaned = sanitize_error_message(raw_message)
    assert "secret_live_token_123456" not in cleaned
    assert "ghp_999988887777" not in cleaned
    assert "[REDACTED]" in cleaned
