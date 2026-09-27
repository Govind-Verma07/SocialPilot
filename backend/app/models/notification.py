"""
app/models/notification.py
--------------------------
SQLAlchemy ORM model for the `notifications` table.

Notification Module — Milestone 4:
  Fields:
    id, user_id, type, title, message, is_read, created_at, read_at,
    related_entity_type, related_entity_id, meta_data
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Boolean, DateTime, JSON
from sqlalchemy import ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    """
    Persistent notification record for a user.
    Notifications survive page refreshes and are user-isolated.
    """
    __tablename__ = "notifications"
    __table_args__ = (
        # Idempotency guard: one notification per unique event key per user
        UniqueConstraint("user_id", "idempotency_key", name="uq_notification_user_idempotency"),
        Index("ix_notifications_user_is_read", "user_id", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Notification type: post_published, post_failed, post_scheduled,
    # campaign_created, campaign_updated, campaign_completed, account_issue, system_alert
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Optional link back to the triggering entity (post, campaign, social_account, etc.)
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    related_entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Flexible JSON metadata (platform name, url, error details, etc.)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Real email delivery tracking (pending | sent | failed | skipped)
    email_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        default=None,
        index=True,
    )
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    email_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Idempotency key prevents duplicate notifications for the same event.
    # Format: "{type}:{entity_type}:{entity_id}" or more specific
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.id} user_id={self.user_id} "
            f"type={self.type} is_read={self.is_read}>"
        )
