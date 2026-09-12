"""
app/models/publishing_job.py
-----------------------------
ORM model for Phase 8: Publishing Queue + Retry Handling.
Tracks per-platform publishing jobs, attempts, backoff retries, and errors.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, DateTime, Integer,
    ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PublishingJobStatus


class PublishingJob(Base):
    """
    Represents an isolated, per-platform publishing attempt for a post.
    Enables independent retries, exponential backoff, and idempotent claiming.
    """
    __tablename__ = "publishing_jobs"

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
    social_account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=PublishingJobStatus.queued.value,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("post_id", "social_account_id", name="uq_post_social_account_job"),
    )

    # Relationships
    post = relationship("Post", back_populates="publishing_jobs")
    social_account = relationship("SocialAccount", lazy="joined")
