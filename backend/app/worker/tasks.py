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
            logger.info(f"Dispatching due post #{post.id} (scheduled_at={post.scheduled_at})")
            try:
                jobs = enqueue_publishing_jobs(db, post.id)
                for j in jobs:
                    process_publishing_job.delay(j.id)
            except Exception as e:
                logger.warning(f"Could not enqueue jobs for due post #{post.id}: {e}")
            publish_single_post_task.delay(post.id)
            dispatched_ids.append(post.id)

        # Also process any retrying jobs whose backoff time has elapsed
        retry_res = process_queued_and_retry_jobs()

        return {
            "dispatched_count": len(dispatched_ids),
            "post_ids": dispatched_ids,
            "retry_dispatched_count": retry_res["dispatched_count"],
        }
    finally:
        db.close()
