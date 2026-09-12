"""
app/models/post_publish_result.py
---------------------------------
ORM model for Phase 5: Social Media Publishing Results.
Records per-platform publishing results for each post and target social account.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String, Text, DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PostPublishResult(Base):
    """
    Result of a publishing attempt to a specific social account/platform for a post.
    Enables tracking multi-account and multi-platform publishing outcomes independently.
    """
    __tablename__ = "post_publish_results"

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
    social_account_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("social_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="published",  # "published" or "failed"
        index=True,
    )
    platform_post_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    published_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    post = relationship("Post", back_populates="publish_results")
    social_account = relationship("SocialAccount", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<PostPublishResult id={self.id} post_id={self.post_id} "
            f"platform={self.platform} status={self.status}>"
        )
