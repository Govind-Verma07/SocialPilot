"""
app/services/notification_service.py
-------------------------------------
Centralized notification service for the SocialPilot Notification Module (Milestone 4).

All notification creation goes through this service to ensure:
- Consistent field population
- User notification preferences enforcement (in_app & email channels)
- Idempotency & duplicate prevention (one notification per unique event key)
- Real asynchronous email delivery via Celery & SMTP
- Safe failure handling (email errors never roll back business operations)
- User isolation

Notification types:
  post_published      — post successfully published to a platform
  post_failed         — post publishing failed permanently
  post_scheduled      — post newly scheduled
  scheduled_reminder  — advance reminder for scheduled post (30m before)
  campaign_created    — new campaign created
  campaign_updated    — campaign details updated
  campaign_completed  — campaign reached end date / deliverables completed
  account_issue       — social account auth/token problem
  system_alert        — general system-level information
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.notification import Notification
from app.models.user_settings import UserSettings
from app.models.post import Post

logger = logging.getLogger("socialpilot.notifications")


# ---------------------------------------------------------------------------
# Notification type constants
# ---------------------------------------------------------------------------
class NotificationType:
    POST_PUBLISHED      = "post_published"
    POST_FAILED         = "post_failed"
    POST_SCHEDULED      = "post_scheduled"
    SCHEDULED_REMINDER  = "scheduled_reminder"
    CAMPAIGN_CREATED    = "campaign_created"
    CAMPAIGN_UPDATED    = "campaign_updated"
    CAMPAIGN_COMPLETED  = "campaign_completed"
    ACCOUNT_ISSUE       = "account_issue"
    SYSTEM_ALERT        = "system_alert"


# ---------------------------------------------------------------------------
# Asynchronous email queue helper
# ---------------------------------------------------------------------------
def _dispatch_email_task_safely(notification_id: str):
    """
    Fire-and-forget helper to dispatch the Celery email task.
    Safely handles cases where Celery broker is offline or during testing.
    """
    try:
        from app.worker.tasks import send_notification_email_task
        # Try Celery async dispatch
        send_notification_email_task.delay(notification_id)
        logger.debug(f"Dispatched async email task for notification #{notification_id}")
    except Exception as exc:
        logger.info(f"Could not dispatch async Celery email task ({exc}). Running inline or marking pending.")
        try:
            # Fallback: execute task synchronously if Celery broker is unavailable
            from app.worker.tasks import send_notification_email_task
            send_notification_email_task(notification_id)
        except Exception as inline_exc:
            logger.warning(f"Inline email task execution error (non-fatal): {inline_exc}")


# ---------------------------------------------------------------------------
# Core creation helper
# ---------------------------------------------------------------------------
def create_notification(
    db: Session,
    user_id: str,
    type: str,
    title: str,
    message: str,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[str] = None,
    meta_data: Optional[dict] = None,
    idempotency_key: Optional[str] = None,
    force_email: bool = False,
) -> Optional[Notification]:
    """
    Create and persist a new notification for a user.

    Flow:
    1. Check user preferences for `in_app` and `email` channels.
    2. If `idempotency_key` is supplied and a notification with the same
       (user_id, idempotency_key) pair already exists, the existing record
       is returned without creating duplicates.
    3. If email is enabled for this event, queues Celery email task.
    4. Returns the Notification instance, or None on unexpected error.
    """
    # 1. Check user notification preferences
    settings_obj = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    in_app_enabled = True
    email_enabled = True

    if settings_obj:
        in_app_enabled = settings_obj.is_channel_enabled(type, "in_app")
        email_enabled = settings_obj.is_channel_enabled(type, "email") or force_email

    initial_email_status = "pending" if email_enabled else "skipped"

    try:
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            is_read=False if in_app_enabled else True,  # If in-app is disabled, mark read
            created_at=datetime.now(timezone.utc),
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            meta_data=meta_data or {},
            idempotency_key=idempotency_key,
            email_status=initial_email_status,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        logger.debug(
            f"Created notification [{type}] for user={user_id} "
            f"(entity={related_entity_type}:{related_entity_id}, email_status={initial_email_status})"
        )

        # 2. If email channel is active, queue async email task
        if email_enabled:
            _dispatch_email_task_safely(notif.id)

        return notif

    except IntegrityError:
        db.rollback()
        # Idempotency constraint hit — notification already exists for this unique event
        if idempotency_key:
            existing = (
                db.query(Notification)
                .filter(
                    Notification.user_id == user_id,
                    Notification.idempotency_key == idempotency_key,
                )
                .first()
            )
            logger.debug(
                f"Notification idempotency hit for key={idempotency_key}, user={user_id}. "
                "Returning existing record without re-sending."
            )
            return existing
        return None
    except Exception as exc:
        db.rollback()
        logger.error(f"Failed to create notification: {exc}", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Typed helpers
# ---------------------------------------------------------------------------
def create_post_notification(
    db: Session,
    user_id: str,
    post_id: str,
    event: str,
    platform: Optional[str] = None,
    post_content_preview: Optional[str] = None,
    error_message: Optional[str] = None,
    published_url: Optional[str] = None,
    scheduled_at_str: Optional[str] = None,
) -> Optional[Notification]:
    """
    Create a notification for a post lifecycle event.
    event: 'published' | 'failed' | 'scheduled' | 'reminder'
    """
    platform_label = platform.title() if platform else "your social account"

    if event == "published":
        ntype = NotificationType.POST_PUBLISHED
        title = "Post Published Successfully"
        message = f"Your scheduled post has been successfully published on {platform_label}."
    elif event == "failed":
        ntype = NotificationType.POST_FAILED
        title = "Publishing Failed"
        err = f" Reason: {error_message}" if error_message else ""
        message = f"Your scheduled post could not be published on {platform_label}.{err}"
    elif event == "scheduled":
        ntype = NotificationType.POST_SCHEDULED
        title = "Post Scheduled"
        message = f"Your post has been scheduled for publishing on {platform_label}."
    elif event == "reminder":
        ntype = NotificationType.SCHEDULED_REMINDER
        title = "Scheduled Post Reminder"
        time_info = f" ({scheduled_at_str})" if scheduled_at_str else " soon"
        message = f"Your post on {platform_label} is scheduled to publish{time_info}."
    else:
        logger.warning(f"Unknown post notification event: {event}")
        return None

    # Idempotency key: one notification per (type, post, platform)
    idem_key = f"{ntype}:post:{post_id}:{platform or 'all'}"

    meta: dict = {}
    if platform:
        meta["platform"] = platform
    if post_content_preview:
        meta["preview"] = post_content_preview[:150]
    if published_url:
        meta["published_url"] = published_url
    if error_message:
        meta["error"] = error_message[:500]
    if scheduled_at_str:
        meta["scheduled_at"] = scheduled_at_str

    return create_notification(
        db=db,
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        related_entity_type="post",
        related_entity_id=post_id,
        meta_data=meta,
        idempotency_key=idem_key,
    )


def notify_post_published(
    db: Session,
    post: Post,
    platform: Optional[str] = None,
    published_url: Optional[str] = None,
) -> Optional[Notification]:
    """Convenience helper called upon successful post publishing."""
    preview = (post.content or "")[:150] if post else None
    return create_post_notification(
        db=db,
        user_id=post.user_id,
        post_id=post.id,
        event="published",
        platform=platform,
        post_content_preview=preview,
        published_url=published_url,
    )


def notify_post_failed(
    db: Session,
    post: Post,
    platform: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[Notification]:
    """Convenience helper called upon permanent post publishing failure."""
    preview = (post.content or "")[:150] if post else None
    return create_post_notification(
        db=db,
        user_id=post.user_id,
        post_id=post.id,
        event="failed",
        platform=platform,
        post_content_preview=preview,
        error_message=error_message,
    )


def notify_post_scheduled(
    db: Session,
    post: Post,
    platform: Optional[str] = None,
) -> Optional[Notification]:
    """Convenience helper called when a post is newly scheduled."""
    preview = (post.content or "")[:150] if post else None
    sched_str = post.scheduled_at.isoformat() if post.scheduled_at else None
    return create_post_notification(
        db=db,
        user_id=post.user_id,
        post_id=post.id,
        event="scheduled",
        platform=platform,
        post_content_preview=preview,
        scheduled_at_str=sched_str,
    )


def notify_scheduled_reminder(
    db: Session,
    post: Post,
    platform: Optional[str] = None,
) -> Optional[Notification]:
    """Convenience helper called to send a scheduled post advance reminder."""
    preview = (post.content or "")[:150] if post else None
    sched_str = post.scheduled_at.strftime("%Y-%m-%d %H:%M UTC") if post.scheduled_at else "in ~30 minutes"
    return create_post_notification(
        db=db,
        user_id=post.user_id,
        post_id=post.id,
        event="reminder",
        platform=platform,
        post_content_preview=preview,
        scheduled_at_str=sched_str,
    )


def create_campaign_notification(
    db: Session,
    user_id: str,
    campaign_id: str,
    campaign_name: str,
    event: str,
) -> Optional[Notification]:
    """
    Create a notification for a campaign lifecycle event.
    event: 'created' | 'updated' | 'completed'
    """
    if event == "created":
        ntype = NotificationType.CAMPAIGN_CREATED
        title = "Campaign Created"
        message = f"Your campaign \"{campaign_name}\" has been successfully created."
    elif event == "updated":
        ntype = NotificationType.CAMPAIGN_UPDATED
        title = "Campaign Updated"
        message = f"Campaign \"{campaign_name}\" has been updated."
    elif event == "completed":
        ntype = NotificationType.CAMPAIGN_COMPLETED
        title = "Campaign Completed"
        message = f"Campaign \"{campaign_name}\" has been completed."
    else:
        logger.warning(f"Unknown campaign notification event: {event}")
        return None

    idem_key = None
    if event in ("created", "completed"):
        idem_key = f"{ntype}:campaign:{campaign_id}"

    return create_notification(
        db=db,
        user_id=user_id,
        type=ntype,
        title=title,
        message=message,
        related_entity_type="campaign",
        related_entity_id=campaign_id,
        meta_data={"campaign_name": campaign_name, "event": event},
        idempotency_key=idem_key,
    )


def notify_campaign_event(
    db: Session,
    user_id: str,
    campaign_id: str,
    campaign_name: str,
    event: str,
) -> Optional[Notification]:
    """Convenience alias for campaign events."""
    return create_campaign_notification(
        db=db,
        user_id=user_id,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        event=event,
    )


def create_account_notification(
    db: Session,
    user_id: str,
    account_id: str,
    platform: str,
    issue_description: str,
) -> Optional[Notification]:
    """Create a notification for social account connectivity issues."""
    platform_label = platform.title() if platform else "Social"
    title = f"{platform_label} Account Issue"
    message = f"There is an issue with your {platform_label} account: {issue_description}"

    idem_key = f"{NotificationType.ACCOUNT_ISSUE}:account:{account_id}"

    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.ACCOUNT_ISSUE,
        title=title,
        message=message,
        related_entity_type="social_account",
        related_entity_id=account_id,
        meta_data={"platform": platform, "issue": issue_description},
        idempotency_key=idem_key,
    )


def notify_account_issue(
    db: Session,
    user_id: str,
    account_id: str,
    platform: str,
    issue_description: str,
) -> Optional[Notification]:
    """Convenience alias for social account issues."""
    return create_account_notification(
        db=db,
        user_id=user_id,
        account_id=account_id,
        platform=platform,
        issue_description=issue_description,
    )


def create_system_notification(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    idempotency_key: Optional[str] = None,
    meta_data: Optional[dict] = None,
) -> Optional[Notification]:
    """Create a system-level notification for a user."""
    return create_notification(
        db=db,
        user_id=user_id,
        type=NotificationType.SYSTEM_ALERT,
        title=title,
        message=message,
        related_entity_type=None,
        related_entity_id=None,
        meta_data=meta_data or {},
        idempotency_key=idempotency_key,
    )


def notify_system_alert(
    db: Session,
    user_id: str,
    title: str,
    message: str,
    idempotency_key: Optional[str] = None,
) -> Optional[Notification]:
    """Convenience alias for system alerts."""
    return create_system_notification(
        db=db,
        user_id=user_id,
        title=title,
        message=message,
        idempotency_key=idempotency_key,
    )


# ---------------------------------------------------------------------------
# Query & Management helpers
# ---------------------------------------------------------------------------
def get_user_notifications(
    db: Session,
    user_id: str,
    unread_only: bool = False,
    notification_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[Notification], int]:
    """
    Return paginated notifications for a user, newest first.
    Strictly isolated to user_id.
    """
    q = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        q = q.filter(Notification.is_read == False)
    if notification_type:
        q = q.filter(Notification.type == notification_type)

    total = q.count()
    items = q.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
    return items, total


def get_unread_count(db: Session, user_id: str) -> int:
    """Return the number of unread notifications for a user."""
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .count()
    )


def mark_notification_read(
    db: Session,
    notification_id: str,
    user_id: str,
) -> Optional[Notification]:
    """
    Mark a single notification as read. Enforces user ownership.
    """
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not notif:
        return None
    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notif)
    return notif


def mark_all_read(db: Session, user_id: str) -> int:
    """
    Mark all unread notifications for a user as read.
    """
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == False)
        .update({"is_read": True, "read_at": now}, synchronize_session="fetch")
    )
    db.commit()
    return rows


def delete_notification(
    db: Session,
    notification_id: str,
    user_id: str,
) -> bool:
    """
    Delete a notification by ID. Enforces user ownership.
    """
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not notif:
        return False
    db.delete(notif)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# User Preferences helpers
# ---------------------------------------------------------------------------
def get_user_preferences(db: Session, user_id: str) -> Dict[str, Any]:
    """Retrieve or initialize notification preferences for a user."""
    settings_obj = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=user_id)
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return {
        "email_notifications": settings_obj.email_notifications,
        "preferences": settings_obj.get_notification_preferences(),
    }


def update_user_preferences(db: Session, user_id: str, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Update granular notification preferences for a user."""
    settings_obj = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=user_id)
        db.add(settings_obj)

    if "email_notifications" in payload_dict and payload_dict["email_notifications"] is not None:
        settings_obj.email_notifications = bool(payload_dict["email_notifications"])

    if "preferences" in payload_dict and isinstance(payload_dict["preferences"], dict):
        settings_obj.set_notification_preferences(payload_dict["preferences"])

    db.commit()
    db.refresh(settings_obj)
    return {
        "email_notifications": settings_obj.email_notifications,
        "preferences": settings_obj.get_notification_preferences(),
    }
