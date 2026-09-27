"""
app/worker/tasks.py
-------------------
Celery tasks for Phase 6: Automated Social Media Publishing.

Provides:
- check_and_publish_due_posts: Periodic Celery Beat task scanning for due scheduled posts.
- publish_single_post_task: Worker task that atomically claims and publishes a post via Phase 5 PublishingService.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.enums import PostStatus
from app.models.post import Post
from app.services.publishing.service import PublishingService
from app.worker.celery_app import celery_app

logger = logging.getLogger("socialpilot.worker")


def get_due_posts_query(db: Session, now_utc: datetime):
    """
    Returns query for posts eligible for automated publishing:
    status == SCHEDULED and scheduled_at <= now_utc.
    Also recovers stale posts stuck in PUBLISHING for > 5 minutes.
    """
    from datetime import timedelta
    from sqlalchemy import or_, and_
    stale_threshold = now_utc - timedelta(minutes=5)
    return (
        db.query(Post)
        .filter(
            Post.scheduled_at.isnot(None),
            Post.scheduled_at <= now_utc,
            or_(
                Post.status == PostStatus.scheduled.value,
                and_(
                    Post.status == PostStatus.publishing.value,
                    Post.updated_at <= stale_threshold,
                ),
            ),
        )
        .order_by(Post.scheduled_at.asc())
    )


def claim_post_for_publishing(db: Session, post_id: str) -> bool:
    """
    Atomically transitions a post from SCHEDULED to PUBLISHING.
    Also allows claiming if post was stuck in PUBLISHING for > 5 minutes.
    Returns True if successfully claimed by this worker, False if already claimed.
    """
    from datetime import timedelta
    from sqlalchemy import or_, and_
    now_utc = datetime.now(timezone.utc)
    stale_threshold = now_utc - timedelta(minutes=5)
    rows_updated = (
        db.query(Post)
        .filter(
            Post.id == post_id,
            or_(
                Post.status == PostStatus.scheduled.value,
                and_(
                    Post.status == PostStatus.publishing.value,
                    Post.updated_at <= stale_threshold,
                ),
            ),
        )
        .update(
            {"status": PostStatus.publishing.value, "updated_at": now_utc},
            synchronize_session="fetch",
        )
    )
    db.commit()
    return rows_updated > 0


def process_due_post(db: Session, post_id: str) -> dict:
    """
    Synchronous / asyncio wrapper to claim and publish a post.
    Can be called directly by tests or within a Celery task.
    """
    claimed = claim_post_for_publishing(db, post_id)
    if not claimed:
        logger.info(f"Post #{post_id} already claimed or no longer scheduled. Skipping.")
        return {"post_id": post_id, "claimed": False, "status": "skipped"}

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return {"post_id": post_id, "claimed": True, "status": "not_found"}

    logger.info(f"Claimed post #{post_id}. Executing Phase 5 PublishingService...")

    # Run the async Phase 5 publishing service cleanly in an isolated loop
    loop = asyncio.new_event_loop()
    try:
        updated_post, results = loop.run_until_complete(PublishServiceBridge(db, post))
        final_status = updated_post.status.value if hasattr(updated_post.status, "value") else str(updated_post.status)
        logger.info(f"Post #{post_id} publishing finished with status: {final_status}")
        return {
            "post_id": post_id,
            "claimed": True,
            "status": final_status,
            "results_count": len(results),
        }
    except Exception as exc:
        logger.error(f"Error publishing post #{post_id}: {str(exc)}", exc_info=True)
        post.status = PostStatus.failed.value
        post.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"post_id": post_id, "claimed": True, "status": "failed", "error": str(exc)}
    finally:
        loop.close()


async def PublishServiceBridge(db: Session, post: Post):
    """Bridge call to Phase 5 PublishingService."""
    return await PublishingService.publish_post(db, post)


@celery_app.task(name="app.worker.tasks.publish_single_post_task")
def publish_single_post_task(post_id: str):
    """
    Worker task to publish a single claimed scheduled post.
    """
    db: Session = SessionLocal()
    try:
        return process_due_post(db, post_id)
    finally:
        db.close()


from app.models.publishing_job import PublishingJob
from app.models.enums import PublishingJobStatus
from app.services.publishing.queue_service import (
    enqueue_publishing_jobs,
    claim_publishing_job,
    execute_publishing_job,
)


@celery_app.task(name="app.worker.tasks.process_publishing_job")
def process_publishing_job(job_id: str):
    """
    Phase 8: Worker task that processes a single platform publishing job.
    Atomically claims QUEUED/RETRYING -> PROCESSING.
    Executes platform publisher, handles transient errors and exponential backoff.
    """
    db: Session = SessionLocal()
    try:
        return execute_publishing_job(db, job_id)
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.process_queued_and_retry_jobs")
def process_queued_and_retry_jobs():
    """
    Periodic worker/Beat task that scans for ready retryable PublishingJobs:
    - status == 'retrying' and next_retry_at <= now_utc
    Dispatches each to process_publishing_job.
    """
    now_utc = datetime.now(timezone.utc)
    db: Session = SessionLocal()
    try:
        jobs = (
            db.query(PublishingJob)
            .filter(
                PublishingJob.status == PublishingJobStatus.retrying.value,
                PublishingJob.next_retry_at.isnot(None),
                PublishingJob.next_retry_at <= now_utc,
            )
            .all()
        )
        dispatched = []
        for j in jobs:
            process_publishing_job.delay(j.id)
            dispatched.append(j.id)
        return {"dispatched_count": len(dispatched), "job_ids": dispatched}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.publish_post_task")
def publish_post_task(post_id: str):
    """
    Dedicated asynchronous publishing task alias (Phase 7 & 8).
    Enqueues Phase 8 platform jobs and dispatches each to worker queue.
    """
    db: Session = SessionLocal()
    try:
        jobs = enqueue_publishing_jobs(db, post_id)
        dispatched = []
        for j in jobs:
            process_publishing_job.delay(j.id)
            dispatched.append(j.id)
        return {
            "post_id": post_id,
            "status": "queued",
            "jobs_dispatched": len(dispatched),
            "job_ids": dispatched,
        }
    except Exception as e:
        logger.warning(f"Could not enqueue platform jobs in publish_post_task: {e}")
        return {"post_id": post_id, "status": "failed", "error": str(e)}
    finally:
        db.close()



@celery_app.task(name="app.worker.tasks.check_and_publish_due_posts")
def check_and_publish_due_posts():
    """
    Periodic Celery Beat task scanning for due scheduled posts.
    Finds posts where status=SCHEDULED and scheduled_at <= now_utc.
    Dispatches each due post to publish_single_post_task and enqueues platform jobs.
    """
    now_utc = datetime.now(timezone.utc)
    db: Session = SessionLocal()
    try:
        due_posts: List[Post] = get_due_posts_query(db, now_utc).all()
        logger.info(f"Found {len(due_posts)} due scheduled posts at {now_utc.isoformat()}")

        dispatched_ids = []
        for post in due_posts:
            post_id = post.id
            post_sched = post.scheduled_at
            logger.info(f"Dispatching due post #{post_id} (scheduled_at={post_sched})")
            try:
                jobs = enqueue_publishing_jobs(db, post_id)
                for j in jobs:
                    process_publishing_job.delay(j.id)
            except Exception as e:
                logger.warning(f"Could not enqueue jobs for due post #{post_id}: {e}")
            publish_single_post_task.delay(post_id)
            dispatched_ids.append(post_id)

        # Also process any retrying jobs whose backoff time has elapsed
        retry_res = process_queued_and_retry_jobs()

        return {
            "dispatched_count": len(dispatched_ids),
            "post_ids": dispatched_ids,
            "retry_dispatched_count": retry_res["dispatched_count"],
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Notification Module: Real Email Task & Scheduled Reminders
# ---------------------------------------------------------------------------
from app.models.notification import Notification
from app.models.user import User
from app.models.user_settings import UserSettings
from app.services.email_service import EmailService, EmailTemplates


@celery_app.task(
    name="app.worker.tasks.send_notification_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_notification_email_task(self, notification_id: str):
    """
    Asynchronous Celery task that delivers a real email for a Notification record.
    1. Fetches notification and user records.
    2. Checks idempotency (does not re-send if already 'sent').
    3. Checks user notification preferences.
    4. Renders responsive HTML template according to notification type.
    5. Delivers email via SMTP.
    6. Updates notification email_status, email_sent_at, email_error.
    7. Retries transient connection errors up to max_retries with backoff.
    """
    db: Session = SessionLocal()
    try:
        notif = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notif:
            logger.warning(f"send_notification_email_task: Notification #{notification_id} not found.")
            return {"status": "not_found", "notification_id": notification_id}

        # Idempotency: skip if already sent
        if notif.email_status == "sent":
            logger.info(f"Notification #{notification_id} email already sent at {notif.email_sent_at}. Skipping.")
            return {"status": "already_sent", "notification_id": notification_id}

        user = db.query(User).filter(User.id == notif.user_id).first()
        if not user or not user.email:
            notif.email_status = "failed"
            notif.email_error = "User or email address not found."
            db.commit()
            return {"status": "failed", "error": "User or email not found"}

        # Check user notification preferences
        settings_obj = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
        if settings_obj and not settings_obj.is_channel_enabled(notif.type, "email"):
            notif.email_status = "skipped"
            db.commit()
            logger.info(f"Email skipped for notification #{notification_id} due to user preferences.")
            return {"status": "skipped", "reason": "preferences_disabled"}

        # Build email templates based on type
        meta = notif.meta_data or {}
        ntype = notif.type
        user_name = user.full_name or user.email.split("@")[0]

        if ntype == "post_published":
            subject, html_body, text_body = EmailTemplates.post_published(
                user_name=user_name,
                platform=meta.get("platform", ""),
                preview=meta.get("preview"),
                published_url=meta.get("published_url"),
            )
        elif ntype == "post_failed":
            subject, html_body, text_body = EmailTemplates.post_failed(
                user_name=user_name,
                platform=meta.get("platform", ""),
                preview=meta.get("preview"),
                error_message=meta.get("error") or notif.message,
            )
        elif ntype == "post_scheduled":
            subject, html_body, text_body = EmailTemplates.post_scheduled(
                user_name=user_name,
                platform=meta.get("platform", ""),
                preview=meta.get("preview"),
                scheduled_at_str=meta.get("scheduled_at"),
            )
        elif ntype == "scheduled_reminder":
            subject, html_body, text_body = EmailTemplates.scheduled_reminder(
                user_name=user_name,
                platform=meta.get("platform", ""),
                preview=meta.get("preview"),
                scheduled_at_str=meta.get("scheduled_at"),
            )
        elif ntype in ("campaign_created", "campaign_updated", "campaign_completed"):
            event_suffix = ntype.replace("campaign_", "")
            subject, html_body, text_body = EmailTemplates.campaign_event(
                user_name=user_name,
                campaign_name=meta.get("campaign_name", "Campaign"),
                event=event_suffix,
            )
        elif ntype == "account_issue":
            subject, html_body, text_body = EmailTemplates.account_issue(
                user_name=user_name,
                platform=meta.get("platform", ""),
                issue_description=meta.get("issue") or notif.message,
            )
        elif ntype == "system_alert":
            subject, html_body, text_body = EmailTemplates.system_alert(
                user_name=user_name,
                title=notif.title,
                message=notif.message,
            )
        else:
            subject, html_body, text_body = EmailTemplates.system_alert(
                user_name=user_name,
                title=notif.title,
                message=notif.message,
            )

        # Attempt real SMTP delivery
        success, error_msg = EmailService.send_email(
            to_email=user.email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

        now = datetime.now(timezone.utc)
        if success:
            notif.email_status = "sent"
            notif.email_sent_at = now
            notif.email_error = None
            db.commit()
            return {"status": "sent", "recipient": user.email, "notification_id": notification_id}
        else:
            notif.email_status = "failed"
            notif.email_error = error_msg
            db.commit()

            # Retry on transient connection issues if Celery retry is active
            if self and hasattr(self, "retry"):
                err_lower = (error_msg or "").lower()
                is_transient = any(k in err_lower for k in ("timeout", "connection", "temporary", "network", "busy"))
                if is_transient and self.request.retries < self.max_retries:
                    logger.warning(f"Retrying send_notification_email_task #{notification_id} in {self.default_retry_delay}s")
                    raise self.retry(exc=Exception(error_msg))

            return {"status": "failed", "error": error_msg, "notification_id": notification_id}

    except Exception as exc:
        logger.error(f"Error executing send_notification_email_task for #{notification_id}: {exc}", exc_info=True)
        try:
            notif = db.query(Notification).filter(Notification.id == notification_id).first()
            if notif:
                notif.email_status = "failed"
                notif.email_error = str(exc)[:500]
                db.commit()
        except Exception:
            pass
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.check_and_send_scheduled_reminders")
def check_and_send_scheduled_reminders():
    """
    Periodic Celery Beat task that scans for scheduled posts publishing in the next 30 minutes.
    Dispatches a single reminder notification with an idempotent event key.
    """
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    reminder_window_start = now_utc
    reminder_window_end = now_utc + timedelta(minutes=35)

    db: Session = SessionLocal()
    try:
        from app.services.notification_service import notify_scheduled_reminder
        posts = (
            db.query(Post)
            .filter(
                Post.status == PostStatus.scheduled.value,
                Post.scheduled_at.isnot(None),
                Post.scheduled_at >= reminder_window_start,
                Post.scheduled_at <= reminder_window_end,
            )
            .all()
        )

        dispatched = []
        for p in posts:
            notif = notify_scheduled_reminder(db, p)
            if notif:
                dispatched.append(p.id)

        return {"reminders_checked": len(posts), "dispatched_count": len(dispatched), "post_ids": dispatched}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Analytics Module: Real Social Media Metrics Synchronization Task
# ---------------------------------------------------------------------------

@celery_app.task(name="app.worker.tasks.sync_social_analytics_task")
def sync_social_analytics_task():
    """
    Periodic Celery Beat task that synchronizes real social metrics for published
    posts across all active users. Queries platform APIs (LinkedIn, Facebook,
    Instagram, YouTube, X, Pinterest) and updates PostMetric records.
    """
    import asyncio
    from app.models.user import User
    from app.services.social_analytics_service import SocialAnalyticsService

    db: Session = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()
        logger.info(f"sync_social_analytics_task: Starting sync for {len(users)} active users.")

        total_posts_synced = 0
        total_metrics_updated = 0
        user_results = []

        for user in users:
            try:
                res = asyncio.run(SocialAnalyticsService.sync_user_analytics(db, user.id, days=30))
                total_posts_synced += res.get("synced_posts_count", 0)
                total_metrics_updated += res.get("metrics_updated_count", 0)
                user_results.append({"user_id": user.id, "metrics_updated": res.get("metrics_updated_count", 0)})
            except Exception as u_exc:
                logger.warning(f"Error syncing analytics for user #{user.id}: {u_exc}")

        return {
            "status": "completed",
            "users_processed": len(users),
            "total_posts_synced": total_posts_synced,
            "total_metrics_updated": total_metrics_updated,
        }
    finally:
        db.close()


