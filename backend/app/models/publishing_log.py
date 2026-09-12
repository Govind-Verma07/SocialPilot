"""
app/models/publishing_log.py
----------------------------
ORM model for Phase 9: Publishing Logs & Tracking.
Records detailed timeline events, retry attempts, outcomes, and platform identifiers
for all social media publishing activities.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, DateTime, Integer,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PublishingLog(Base):
    """
    Immutable audit log entry for a publishing lifecycle event.
    Tracks job status transitions, individual attempt numbers, errors,
    and external platform IDs/URLs without leaking secrets.
    """
    __tablename__ = "publishing_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    post_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    publishing_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("publishing_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    social_account_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("social_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    platform_post_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    published_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    post = relationship("Post", back_populates="publishing_logs")
    publishing_job = relationship("PublishingJob")
    social_account = relationship("SocialAccount")
