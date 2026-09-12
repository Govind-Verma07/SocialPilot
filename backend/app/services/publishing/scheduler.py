"""
app/services/publishing/scheduler.py
------------------------------------
In-process automated background scheduler for scheduled social media posts.
Periodically scans for posts where:
    status == 'scheduled' AND scheduled_at <= now_utc
Atomically claims and publishes them automatically across all target channels
without requiring any user interaction.
Non-blocking implementation using worker threads for database queries.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.enums import PostStatus
from app.models.post import Post
from app.services.publishing.service import PublishingService
from app.services.publishing.log_generator import generate_post_audit_log_content
from app.worker.tasks import claim_post_for_publishing

logger = logging.getLogger("socialpilot.scheduler")

_scheduler_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None


def _get_due_post_ids() -> List[str]:
    """Runs in a separate thread: queries IDs of posts due for publishing."""
    db: Session = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        records = (
            db.query(Post.id)
            .filter(
                Post.status == PostStatus.scheduled.value,
                Post.scheduled_at.isnot(None),
                Post.scheduled_at <= now_utc,
            )
            .order_by(Post.scheduled_at.asc())
            .all()
        )
        return [r[0] for r in records]
    except Exception as exc:
        logger.warning(f"[Scheduler] Could not query due posts: {exc}")
        return []
    finally:
        db.close()


def _claim_post(post_id: str) -> bool:
    """Runs in a separate thread: atomically claims a post."""
    db: Session = SessionLocal()
    try:
        return claim_post_for_publishing(db, post_id)
    except Exception as exc:
        logger.warning(f"[Scheduler] Could not claim post #{post_id}: {exc}")
        return False
    finally:
        db.close()


async def check_and_publish_due_posts_once() -> int:
    """
    Checks for due posts and publishes them asynchronously.
    Uses worker threads for synchronous DB queries to prevent blocking the event loop.
    """
    due_ids = await asyncio.to_thread(_get_due_post_ids)
    if not due_ids:
        return 0

    logger.info(f"⏰ [Scheduler] Found {len(due_ids)} due scheduled post(s) to publish automatically.")
    published_count = 0

    for post_id in due_ids:
        claimed = await asyncio.to_thread(_claim_post, post_id)
        if not claimed:
            logger.info(f"Post #{post_id} already claimed or no longer scheduled. Skipping.")
            continue

        logger.info(f"🚀 [Scheduler] Auto-publishing claimed post #{post_id}...")
        db: Session = SessionLocal()
        try:
            p = db.query(Post).filter(Post.id == post_id).first()
            if not p:
                continue

            updated_post, results = await PublishingService.publish_post(db, p)

            # Generate real content log file
            try:
                generate_post_audit_log_content(db, updated_post)
            except Exception as log_err:
                logger.warning(f"Could not generate log for post #{post_id}: {log_err}")

            logger.info(
                f"✅ [Scheduler] Post #{post_id} auto-published. Status: {updated_post.status}, Accounts: {len(results)}"
            )
            published_count += 1
        except Exception as exc:
            logger.error(f"❌ [Scheduler] Failed to publish post #{post_id}: {exc}", exc_info=True)
            try:
                p = db.query(Post).filter(Post.id == post_id).first()
                if p:
                    p.status = PostStatus.failed.value
                    p.updated_at = datetime.now(timezone.utc)
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    return published_count


async def scheduled_posts_worker_loop(interval_seconds: int = 15):
    """Continuous background loop running inside FastAPI process."""
    logger.info(f"⏱️ Automated publishing background worker started (interval: {interval_seconds}s).")
    # Initial sleep to allow uvicorn to finish startup cleanly
    await asyncio.sleep(2)

    while _stop_event and not _stop_event.is_set():
        try:
            await check_and_publish_due_posts_once()
        except Exception as exc:
            logger.error(f"Error in scheduler worker cycle: {exc}", exc_info=True)

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=interval_seconds)
            break
        except asyncio.TimeoutError:
            pass


def start_scheduler(interval_seconds: int = 15):
    """Starts the background scheduler task inside FastAPI."""
    global _scheduler_task, _stop_event
    if _scheduler_task and not _scheduler_task.done():
        return
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(scheduled_posts_worker_loop(interval_seconds=interval_seconds))
    logger.info("✅ SocialPilot Background Scheduler started successfully.")


def stop_scheduler():
    """Stops the background scheduler task cleanly on FastAPI shutdown."""
    global _scheduler_task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
    logger.info("🛑 SocialPilot Background Scheduler stopped.")
