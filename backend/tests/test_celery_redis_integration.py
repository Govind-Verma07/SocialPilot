"""
tests/test_celery_redis_integration.py
---------------------------------------
End-to-end integration tests verifying Redis + Celery configuration,
task registration, Celery Beat periodic schedule, asynchronous task dispatch,
duplicate worker prevention (atomic claiming), retry queue processing,
and recurring post compatibility.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
import pytest
import httpx

from app.core.config import settings
from app.models.enums import (
    PostStatus,
    SocialPlatform,
    AccountStatus,
    PublishingJobStatus,
    RecurrenceFrequency,
)
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.models.publishing_job import PublishingJob
from app.models.recurring_rule import RecurringRule, RecurringRuleSocialAccount
from app.core.encryption import encrypt_token
from app.worker.celery_app import celery_app
from app.worker.tasks import (
    publish_single_post_task,
    process_publishing_job,
    process_queued_and_retry_jobs,
    publish_post_task,
    check_and_publish_due_posts,
    claim_post_for_publishing,
    get_due_posts_query,
)
from app.services.publishing.queue_service import enqueue_publishing_jobs


def _register_and_login(client, email: str, name: str = "Celery Test User"):
    res = client.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "Password123"},
    )
    assert res.status_code == 201
    data = res.json()
    return data["user"]["id"], data["access_token"], {"Authorization": f"Bearer {data['access_token']}"}


def _seed_account(db_session, user_id: str, platform: SocialPlatform, name: str = "Test Channel"):
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_acc_{user_id[:6]}",
        account_name=name,
        account_username=f"{platform.value}_handle",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("mock-token"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


# ==============================================================================
# 1. Configuration & Celery App Verification
# ==============================================================================
def test_1_redis_and_celery_configuration():
    """Verify Redis URLs and Celery configurations in application settings."""
    assert settings.REDIS_URL.startswith("redis://")
    assert settings.CELERY_BROKER_URL.startswith("redis://")
    assert settings.CELERY_RESULT_BACKEND.startswith("redis://")
    assert isinstance(settings.ENABLE_INPROCESS_SCHEDULER, bool)

    assert celery_app.main == "socialpilot_worker"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.timezone == "UTC"
    assert celery_app.conf.enable_utc is True


def test_2_celery_task_registration():
    """Verify all background publishing tasks are registered with Celery."""
    registered_tasks = celery_app.tasks

    expected_tasks = [
        "app.worker.tasks.publish_single_post_task",
        "app.worker.tasks.process_publishing_job",
        "app.worker.tasks.process_queued_and_retry_jobs",
        "app.worker.tasks.publish_post_task",
        "app.worker.tasks.check_and_publish_due_posts",
    ]
    for task_name in expected_tasks:
        assert task_name in registered_tasks, f"Task {task_name} missing from Celery registry"


def test_3_celery_beat_schedule_structure():
    """Verify Celery Beat periodic schedule contains expected recurring monitors."""
    schedule = celery_app.conf.beat_schedule
    assert "check-due-scheduled-posts-periodically" in schedule
    assert "process-queued-and-retry-jobs" in schedule

    due_scan = schedule["check-due-scheduled-posts-periodically"]
    assert due_scan["task"] == "app.worker.tasks.check_and_publish_due_posts"
    assert due_scan["schedule"] == 15.0

    retry_scan = schedule["process-queued-and-retry-jobs"]
    assert retry_scan["task"] == "app.worker.tasks.process_queued_and_retry_jobs"
    assert retry_scan["schedule"] == 30.0


# ==============================================================================
# 2. Celery Worker Task Execution & Atomic Claiming
# ==============================================================================
def test_4_duplicate_worker_protection_atomic_claiming(db_session):
    """
    Verify atomic post claiming prevents duplicate execution across multiple workers.
    Only the first worker to claim a scheduled post succeeds; subsequent workers get False.
    """
    now = datetime.now(timezone.utc)
    post = Post(
        user_id="user-claim-1",
        content="Testing atomic claiming",
        status=PostStatus.scheduled.value,
        scheduled_at=now - timedelta(minutes=1),
    )
    db_session.add(post)
    db_session.commit()

    # First worker attempt
    claimed_1 = claim_post_for_publishing(db_session, post.id)
    assert claimed_1 is True

    db_session.refresh(post)
    assert post.status == PostStatus.publishing.value

    # Second worker attempt on the same post
    claimed_2 = claim_post_for_publishing(db_session, post.id)
    assert claimed_2 is False  # Already in publishing status — safe skip!


def test_5_scheduled_posts_queried_and_dispatched_via_beat_task(client, db_session):
    """
    Verify check_and_publish_due_posts finds due posts in PostgreSQL,
    enqueues per-platform jobs, and dispatches Celery publishing tasks.
    """
    user_id, _, _ = _register_and_login(client, "beat_celery@test.com", "Beat Tester")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Beat LinkedIn")
    now = datetime.now(timezone.utc)

    # Post due 5 minutes ago
    post = Post(
        user_id=user_id,
        content="Scheduled post picked up by Celery Beat",
        status=PostStatus.scheduled.value,
        scheduled_at=now - timedelta(minutes=5),
    )
    db_session.add(post)
    db_session.commit()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    with patch("app.worker.tasks.SessionLocal", return_value=db_session), \
         patch("app.worker.tasks.publish_single_post_task.delay") as mock_single_task, \
         patch("app.worker.tasks.process_publishing_job.delay") as mock_job_task:
        result = check_and_publish_due_posts()

    assert result["dispatched_count"] >= 1
    assert post.id in result["post_ids"]
    mock_single_task.assert_any_call(post.id)
    mock_job_task.assert_called()


def test_6_manual_publish_dispatches_celery_task(client, db_session):
    """
    Verify manual publish with async_publish=True enqueues Celery jobs and tasks.
    """
    user_id, _, headers = _register_and_login(client, "manual_async@test.com", "Async Publisher")
    acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "Async FB")
    now = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post for manual async Celery publishing",
        status=PostStatus.scheduled.value,
        scheduled_at=now + timedelta(days=1),
    )
    db_session.add(post)
    db_session.commit()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    with patch("app.worker.tasks.process_publishing_job.delay") as mock_job_delay, \
         patch("app.worker.tasks.publish_post_task.delay") as mock_task_delay:
        res = client.post(f"/api/v1/posts/{post.id}/publish?async_publish=true", headers=headers)

    assert res.status_code == 200
    mock_job_delay.assert_called_once()
    mock_task_delay.assert_called_once_with(post.id)


def test_7_retry_queue_scan_dispatches_ready_jobs(client, db_session):
    """
    Verify process_queued_and_retry_jobs scans for retrying PublishingJobs
    whose next_retry_at has arrived, and dispatches them via Celery.
    """
    user_id, _, _ = _register_and_login(client, "retry_scan@test.com", "Retry Tester")
    acc = _seed_account(db_session, user_id, SocialPlatform.x, "Retry X")
    now = datetime.now(timezone.utc)

    post = Post(
        user_id=user_id,
        content="Post with retrying job",
        status=PostStatus.publishing.value,
    )
    db_session.add(post)
    db_session.commit()

    # Job eligible for retry (next_retry_at was 2 minutes ago)
    job = PublishingJob(
        post_id=post.id,
        social_account_id=acc.id,
        status=PublishingJobStatus.retrying.value,
        attempt_count=1,
        max_attempts=3,
        next_retry_at=now - timedelta(minutes=2),
    )
    db_session.add(job)
    db_session.commit()

    with patch("app.worker.tasks.SessionLocal", return_value=db_session), \
         patch("app.worker.tasks.process_publishing_job.delay") as mock_job_delay:
        res = process_queued_and_retry_jobs()

    assert res["dispatched_count"] >= 1
    assert job.id in res["job_ids"]
    mock_job_delay.assert_any_call(job.id)


def test_8_recurring_posts_compatible_with_celery_dispatch(client, db_session):
    """
    Verify that occurrences created by recurring rules are properly picked up
    by the Celery Beat due query.
    """
    user_id, _, headers = _register_and_login(client, "recurring_celery@test.com", "Recur User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Recur LI")
    now = datetime.now(timezone.utc)

    # Create daily recurring schedule
    rule_payload = {
        "content": "Daily recurring post driven by Celery Beat",
        "social_account_ids": [acc.id],
        "frequency": "daily",
        "start_at": (now + timedelta(hours=1)).isoformat(),
        "end_at": (now + timedelta(days=3)).isoformat(),
        "post_type": "text",
    }
    res = client.post("/api/v1/recurring-posts", json=rule_payload, headers=headers)
    assert res.status_code == 201

    # Query due posts with timestamp after start_at
    due_posts = get_due_posts_query(db_session, now + timedelta(hours=2)).all()
    recurring_due = [p for p in due_posts if p.recurring_rule_id is not None]
    assert len(recurring_due) >= 1
