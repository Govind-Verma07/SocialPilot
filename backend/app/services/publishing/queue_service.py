"""
app/services/publishing/queue_service.py
----------------------------------------
Publishing Queue & Retry Management for Phase 8.
Handles:
- Per-platform PublishingJob creation and duplicate prevention
- Transient vs permanent error classification
- Exponential retry backoff calculation
- Atomic claiming of jobs
- Independent execution per social platform
- Post status aggregation across platform jobs
"""

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import PostStatus, PublishingJobStatus, PublishingLogEventType
from app.models.post import Post
from app.models.publishing_job import PublishingJob
from app.models.publishing_log import PublishingLog
from app.models.post_publish_result import PostPublishResult
from app.models.social_account import SocialAccount
from app.services.publishing.adapters import get_publisher
from app.services.publishing.base import PublishResult

logger = logging.getLogger("socialpilot.queue")


def sanitize_error_message(msg: Optional[str]) -> Optional[str]:
    """Sanitize sensitive keys, bearer tokens, or secrets from error logs."""
    if not msg:
        return msg
    # Strip bearer authorization tokens
    sanitized = re.sub(r'Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*', 'Bearer [REDACTED]', msg, flags=re.IGNORECASE)
    # Strip token=, key=, secret= query params or key-values
    sanitized = re.sub(r'(token|access_token|secret|key)=([A-Za-z0-9\-\._~\+\/]+)', r'\1=[REDACTED]', sanitized, flags=re.IGNORECASE)
    return sanitized


def create_publishing_log(
    db: Session,
    post_id: str,
    platform: str,
    event_type: str,
    status: str,
    publishing_job_id: Optional[str] = None,
    social_account_id: Optional[str] = None,
    attempt_number: int = 1,
    platform_post_id: Optional[str] = None,
    published_url: Optional[str] = None,
    error_message: Optional[str] = None,
) -> PublishingLog:
    """
    Creates and commits a new PublishingLog record for Phase 9 audit and tracking.
    """
    clean_error = sanitize_error_message(error_message)
    log_entry = PublishingLog(
        post_id=post_id,
        publishing_job_id=publishing_job_id,
        social_account_id=social_account_id,
        platform=platform,
        event_type=event_type,
        status=status,
        attempt_number=attempt_number,
        platform_post_id=platform_post_id,
        published_url=published_url,
        error_message=clean_error,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry

# Keywords and error patterns indicating transient/retryable failures
TRANSIENT_ERROR_PATTERNS = [
    "rate limit",
    "rate_limit",
    "too many requests",
    "429",
    "timeout",
    "timed out",
    "readtimeout",
    "connecttimeout",
    "connection error",
    "connection reset",
    "connecterror",
    "network error",
    "temporary",
    "server error",
    "internal server error",
    "500",
    "502",
    "503",
    "504",
    "bad gateway",
    "service unavailable",
    "gateway timeout",
    "try again",
]

# Keywords indicating permanent/non-retryable failures
PERMANENT_ERROR_PATTERNS = [
    "invalid token",
    "expired token",
    "token expired",
    "expired page token",
    "revoked",
    "unauthorized",
    "401",
    "permission",
    "forbidden",
    "access denied",
    "insufficient scope",
    "403",
    "invalid content",
    "bad request",
    "validation error",
    "400",
    "not found",
    "404",
    "account disconnected",
    "token missing",
    "no attached social accounts",
]


def is_transient_error(error_message: Optional[str]) -> bool:
    """
    Classify whether a publishing failure is transient (retryable) or permanent (fatal).
    Permanent patterns take precedence.
    """
    if not error_message:
        return False

    err_lower = error_message.lower()

    for perm in PERMANENT_ERROR_PATTERNS:
        if perm in err_lower:
            return False

    for trans in TRANSIENT_ERROR_PATTERNS:
        if trans in err_lower:
            return True

    return False


def get_backoff_delay(attempt_count: int) -> int:
    """
    Calculate backoff delay in seconds for a retry attempt.
    Default backoff progression: ~1 min (60s) -> 5 min (300s) -> 15 min (900s).
    """
    try:
        schedule = [int(s.strip()) for s in settings.PUBLISH_RETRY_BACKOFF_SECONDS.split(",") if s.strip()]
    except Exception:
        schedule = [60, 300, 900]

    if not schedule:
        schedule = [60, 300, 900]

    idx = max(0, min(attempt_count - 1, len(schedule) - 1))
    return schedule[idx]


def enqueue_publishing_jobs(db: Session, post_id: str) -> List[PublishingJob]:
    """
    Creates or re-queues one PublishingJob per attached social account for the post.
    Ensures idempotency via (post_id, social_account_id) uniqueness.
    Transitions post status to PUBLISHING.
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise ValueError(f"Post #{post_id} not found.")

    attached_social_ids = [psa.social_account_id for psa in post.social_accounts if psa.social_account_id]
    if not attached_social_ids:
        raise ValueError("Post has no attached social accounts to publish to.")

    now = datetime.now(timezone.utc)
    max_retries = getattr(settings, "MAX_PUBLISH_RETRIES", 3)
    created_or_queued_jobs: List[PublishingJob] = []

    for sa_id in attached_social_ids:
        job = (
            db.query(PublishingJob)
            .filter(
                PublishingJob.post_id == post.id,
                PublishingJob.social_account_id == sa_id,
            )
            .first()
        )

        if not job:
            job = PublishingJob(
                post_id=post.id,
                social_account_id=sa_id,
                status=PublishingJobStatus.queued.value,
                attempt_count=0,
                max_attempts=max_retries,
                next_retry_at=None,
                last_error=None,
                created_at=now,
                updated_at=now,
            )
            db.add(job)
            created_or_queued_jobs.append(job)
        else:
            # If job already published or cancelled, do not re-queue unless it was failed
            if job.status == PublishingJobStatus.failed.value:
                job.status = PublishingJobStatus.queued.value
                job.attempt_count = 0
                job.last_error = None
                job.next_retry_at = None
                job.updated_at = now
                created_or_queued_jobs.append(job)
            elif job.status in (PublishingJobStatus.queued.value, PublishingJobStatus.retrying.value):
                created_or_queued_jobs.append(job)
            # Already published or processing jobs remain as-is

    post.status = PostStatus.publishing.value
    post.updated_at = now
    db.commit()

    for j in created_or_queued_jobs:
        db.refresh(j)
        account = db.query(SocialAccount).filter(SocialAccount.id == j.social_account_id).first()
        platform_str = account.platform.value if account and hasattr(account.platform, "value") else (str(account.platform) if account else "unknown")
        create_publishing_log(
            db,
            post_id=post.id,
            platform=platform_str,
            event_type=PublishingLogEventType.queued.value,
            status=PublishingJobStatus.queued.value,
            publishing_job_id=j.id,
            social_account_id=j.social_account_id,
            attempt_number=j.attempt_count,
        )

    return created_or_queued_jobs


def claim_publishing_job(db: Session, job_id: str) -> bool:
    """
    Atomically transitions a job from QUEUED or RETRYING to PROCESSING.
    Returns True if successfully claimed, False otherwise.
    """
    now = datetime.now(timezone.utc)
    rows = (
        db.query(PublishingJob)
        .filter(
            PublishingJob.id == job_id,
            PublishingJob.status.in_([PublishingJobStatus.queued.value, PublishingJobStatus.retrying.value]),
        )
        .update(
            {
                "status": PublishingJobStatus.processing.value,
                "updated_at": now,
            },
            synchronize_session="fetch",
        )
    )
    db.commit()
    return rows > 0


def recalculate_post_status(db: Session, post_id: str) -> str:
    """
    Evaluates all PublishingJobs for a post and sets overall Post status:
    - If ALL jobs are 'published': post status -> 'published'
    - If any job is still 'queued', 'processing', or 'retrying': post status -> 'publishing'
    - If all jobs have finished and at least one is 'failed': post status -> 'failed'
    """
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        return "not_found"

    jobs = db.query(PublishingJob).filter(PublishingJob.post_id == post_id).all()
    if not jobs:
        return post.status

    statuses = [j.status for j in jobs]
    now = datetime.now(timezone.utc)

    if all(s == PublishingJobStatus.published.value for s in statuses):
        post.status = PostStatus.published.value
        post.published_at = now
    elif any(s in (PublishingJobStatus.queued.value, PublishingJobStatus.processing.value, PublishingJobStatus.retrying.value) for s in statuses):
        post.status = PostStatus.publishing.value
    elif any(s == PublishingJobStatus.failed.value for s in statuses):
        post.status = PostStatus.failed.value
    elif any(s == PublishingJobStatus.cancelled.value for s in statuses):
        post.status = PostStatus.failed.value
    elif any(s == PublishingJobStatus.published.value for s in statuses):
        post.status = PostStatus.published.value
        if not post.published_at:
            post.published_at = now
    else:
        # All jobs skipped
        post.status = PostStatus.failed.value

    post.updated_at = now
    db.commit()
    db.refresh(post)
    return post.status


async def _execute_job_async(db: Session, job: PublishingJob, post: Post, account: SocialAccount) -> PublishResult:
    """Helper to run platform publisher adapter for a single account with resolved media context."""
    from app.services.publishing.media_resolver import resolve_post_publish_context
    platform_str = account.platform.value if hasattr(account.platform, "value") else str(account.platform)
    try:
        context = await resolve_post_publish_context(db, post)

        p_type = (context.post_type or post.post_type or "text").lower().strip()
        media_count = context.media_count

        logger.info(
            f"Queue job #{job.id} pre-check: post_id={post.id}, post_type={p_type}, media_count={media_count}, "
            f"media_ids={[m.media_id for m in context.media_items]}, "
            f"resolved_media_types={[m.media_type for m in context.media_items]}"
        )

        if p_type in ("image", "video", "carousel", "story", "reel") and media_count == 0:
            return PublishResult(
                success=False,
                platform=platform_str,
                error_message=f"Pipeline error: Post format '{p_type.upper()}' requires media attachments, but resolved media_count is 0.",
            )
        if p_type == "carousel" and media_count < 2:
            return PublishResult(
                success=False,
                platform=platform_str,
                error_message=f"Pipeline error: Carousel format requires at least 2 media items, but resolved media_count is {media_count}.",
            )

        publisher = get_publisher(platform_str)
        return await publisher.publish(post, account, context=context)
    except Exception as exc:
        return PublishResult(
            success=False,
            platform=platform_str,
            error_message=str(exc),
        )


def execute_publishing_job(db: Session, job_id: str) -> dict:
    """
    Processes a single PublishingJob:
    1. Atomically claims job (QUEUED/RETRYING -> PROCESSING).
    2. Calls platform publisher adapter.
    3. Records PostPublishResult.
    4. Handles transient error retry with backoff vs permanent failure.
    5. Updates post overall status.
    Returns a serializable dictionary.
    """
    claimed = claim_publishing_job(db, job_id)
    job = db.query(PublishingJob).filter(PublishingJob.id == job_id).first()
    if not job:
        return {"job_id": job_id, "claimed": False, "status": "not_found"}

    if not claimed:
        logger.info(f"Job #{job_id} already claimed or in status '{job.status}'. Skipping.")
        return {"job_id": job_id, "claimed": False, "status": job.status}

    # If job was cancelled while in queue
    if job.status == PublishingJobStatus.cancelled.value:
        account = db.query(SocialAccount).filter(SocialAccount.id == job.social_account_id).first()
        platform_name = account.platform.value if account and hasattr(account.platform, "value") else (str(account.platform) if account else "unknown")
        create_publishing_log(
            db,
            post_id=job.post_id,
            platform=platform_name,
            event_type=PublishingLogEventType.cancelled.value,
            status=PublishingJobStatus.cancelled.value,
            publishing_job_id=job.id,
            social_account_id=job.social_account_id,
            attempt_number=job.attempt_count,
        )
        return {"job_id": job_id, "claimed": False, "status": "cancelled"}

    post = db.query(Post).filter(Post.id == job.post_id).first()
    account = db.query(SocialAccount).filter(SocialAccount.id == job.social_account_id).first()

    if not post or not account:
        job.status = PublishingJobStatus.failed.value
        job.last_error = "Associated Post or SocialAccount no longer exists."
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        recalculate_post_status(db, job.post_id)
        return {"job_id": job_id, "claimed": True, "status": "failed", "error": job.last_error}

    # Increment attempt count
    job.attempt_count += 1
    now = datetime.now(timezone.utc)
    platform_str = account.platform.value if hasattr(account.platform, "value") else str(account.platform)

    # Phase 9: Log PROCESSING and PUBLISHING_STARTED events
    create_publishing_log(
        db,
        post_id=post.id,
        platform=platform_str,
        event_type=PublishingLogEventType.processing.value,
        status=PublishingJobStatus.processing.value,
        publishing_job_id=job.id,
        social_account_id=account.id,
        attempt_number=job.attempt_count,
    )
    create_publishing_log(
        db,
        post_id=post.id,
        platform=platform_str,
        event_type=PublishingLogEventType.publishing_started.value,
        status=PublishingJobStatus.processing.value,
        publishing_job_id=job.id,
        social_account_id=account.id,
        attempt_number=job.attempt_count,
    )

    # Execute platform publisher
    loop = asyncio.new_event_loop()
    try:
        publish_res: PublishResult = loop.run_until_complete(
            _execute_job_async(db, job, post, account)
        )
    finally:
        loop.close()

    if getattr(publish_res, "skipped", False):
        status_str = "skipped"
    elif publish_res.success:
        status_str = "published"
    else:
        status_str = "failed"

    # Persist or update PostPublishResult for Phase 5 result tracking
    result_record = (
        db.query(PostPublishResult)
        .filter(
            PostPublishResult.post_id == post.id,
            PostPublishResult.social_account_id == account.id,
        )
        .first()
    )
    if not result_record:
        result_record = PostPublishResult(
            post_id=post.id,
            social_account_id=account.id,
            platform=platform_str,
            status=status_str,
            platform_post_id=publish_res.platform_post_id,
            published_url=publish_res.published_url,
            error_message=publish_res.error_message,
            published_at=publish_res.published_at or (now if publish_res.success else None),
        )
        db.add(result_record)
    else:
        result_record.status = status_str
        result_record.platform_post_id = publish_res.platform_post_id
        result_record.published_url = publish_res.published_url
        result_record.error_message = publish_res.error_message
        if publish_res.success:
            result_record.published_at = publish_res.published_at or now

    if getattr(publish_res, "skipped", False):
        job.status = PublishingJobStatus.skipped.value
        job.last_error = publish_res.error_message
        job.next_retry_at = None
        logger.info(f"Job #{job_id} on {platform_str} skipped: {publish_res.error_message}")
        create_publishing_log(
            db,
            post_id=post.id,
            platform=platform_str,
            event_type=PublishingLogEventType.skipped.value,
            status=PublishingJobStatus.skipped.value,
            publishing_job_id=job.id,
            social_account_id=account.id,
            attempt_number=job.attempt_count,
            error_message=publish_res.error_message,
        )
    elif publish_res.success:
        job.status = PublishingJobStatus.published.value
        job.last_error = None
        job.next_retry_at = None
        logger.info(f"Job #{job_id} successfully published to {platform_str}.")
        # Phase 9: Log PUBLISHED event
        create_publishing_log(
            db,
            post_id=post.id,
            platform=platform_str,
            event_type=PublishingLogEventType.published.value,
            status=PublishingJobStatus.published.value,
            publishing_job_id=job.id,
            social_account_id=account.id,
            attempt_number=job.attempt_count,
            platform_post_id=publish_res.platform_post_id,
            published_url=publish_res.published_url,
        )
    else:
        job.last_error = publish_res.error_message
        is_transient = is_transient_error(publish_res.error_message)

        if is_transient and job.attempt_count < job.max_attempts:
            job.status = PublishingJobStatus.retrying.value
            delay_sec = get_backoff_delay(job.attempt_count)
            job.next_retry_at = now + timedelta(seconds=delay_sec)
            logger.warning(
                f"Job #{job_id} on {platform_str} encountered transient error (attempt {job.attempt_count}/{job.max_attempts}). "
                f"Scheduled retry in {delay_sec}s at {job.next_retry_at}."
            )
            # Phase 9: Log RETRYING event
            create_publishing_log(
                db,
                post_id=post.id,
                platform=platform_str,
                event_type=PublishingLogEventType.retrying.value,
                status=PublishingJobStatus.retrying.value,
                publishing_job_id=job.id,
                social_account_id=account.id,
                attempt_number=job.attempt_count,
                error_message=publish_res.error_message,
            )
        else:
            job.status = PublishingJobStatus.failed.value
            job.next_retry_at = None
            logger.error(
                f"Job #{job_id} on {platform_str} permanently failed after {job.attempt_count} attempts. "
                f"Error: {publish_res.error_message}"
            )
            # Phase 9: Log FAILED event
            create_publishing_log(
                db,
                post_id=post.id,
                platform=platform_str,
                event_type=PublishingLogEventType.failed.value,
                status=PublishingJobStatus.failed.value,
                publishing_job_id=job.id,
                social_account_id=account.id,
                attempt_number=job.attempt_count,
                error_message=publish_res.error_message,
            )

    job.updated_at = now
    db.commit()

    # Re-evaluate post overall status
    post_status = recalculate_post_status(db, post.id)

    # Generate and persist rich audit log to disk and cache
    try:
        from app.services.publishing.log_generator import generate_post_audit_log_content
        generate_post_audit_log_content(db, post)
    except Exception as log_exc:
        logger.warning(f"Could not generate log for post #{post.id}: {log_exc}")

    return {
        "job_id": job.id,
        "post_id": post.id,
        "social_account_id": account.id,
        "platform": platform_str,
        "job_status": job.status,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "next_retry_at": job.next_retry_at.isoformat() if job.next_retry_at else None,
        "post_status": post_status,
        "error": job.last_error,
    }
