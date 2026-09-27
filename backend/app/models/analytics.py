"""
app/models/analytics.py
-----------------------
ORM model for Milestone 3: Real Content & Social Post Analytics.
Defines:
  post_metrics — Stores granular performance and engagement metrics for published posts.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String, Integer, Boolean, DateTime,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PostMetric(Base):
    """
    Performance and engagement metrics captured for a published post on a specific platform.
    Tracks real impressions, reach, engagement, clicks, video views, likes, comments, and shares.
    """
    __tablename__ = "post_metrics"

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
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reach: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engagement: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    video_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_real: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    post = relationship("Post", back_populates="metrics")
    social_account = relationship("SocialAccount", lazy="joined")

    def __repr__(self) -> str:
        return f"<PostMetric id={self.id} post_id={self.post_id} platform={self.platform} eng={self.engagement}>"
