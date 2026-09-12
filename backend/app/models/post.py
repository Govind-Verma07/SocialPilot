"""
app/models/post.py
------------------
ORM models for Phase 1: Content Scheduling Foundation.
Defines:
  posts               — Scheduled and draft social media posts.
  post_social_accounts — Junction table associating posts with target social accounts.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, DateTime, JSON,
    ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PostStatus


class Post(Base):
    """A social media post created by a user, optionally scheduled for publishing."""
    __tablename__ = "posts"

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
    team_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    post_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    status: Mapped[str] = mapped_column(
        SAEnum(
            PostStatus,
            name="poststatus",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PostStatus.draft,
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    recurring_rule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("recurring_rules.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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

    # Relationships
    social_accounts: Mapped[list["PostSocialAccount"]] = relationship(
        "PostSocialAccount",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    publish_results = relationship(
        "PostPublishResult",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    publishing_jobs = relationship(
        "PublishingJob",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    publishing_logs = relationship(
        "PublishingLog",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    user = relationship("User", foreign_keys=[user_id])
    recurring_rule = relationship("RecurringRule", back_populates="posts")



class PostSocialAccount(Base):
    """Junction table associating a Post with one or more target SocialAccounts."""
    __tablename__ = "post_social_accounts"

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="social_accounts")
    social_account = relationship("SocialAccount", lazy="joined")
