"""
app/models/campaign.py
----------------------
ORM model for Milestone 3: Campaign Management & Performance Tracking.
Defines:
  campaigns — Marketing campaigns organizing posts, budgets, objectives, and tracking metrics.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String, Text, DateTime, Numeric, Integer,
    ForeignKey, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Campaign(Base):
    """
    Marketing campaign domain model.
    Groups posts, defines timeframe, budget, target platform(s), and business objectives.
    """
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint("budget >= 0", name="chk_campaign_budget_non_negative"),
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="chk_campaign_end_date_after_start"),
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
    team_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(String(100), nullable=False, default="multi")
    start_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    end_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    budget: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0.00,
    )
    revenue: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    conversions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    objective: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Brand Awareness",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",  # "active", "scheduled", "completed", "paused", "draft"
        index=True,
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
    posts: Mapped[List["Post"]] = relationship(
        "Post",
        back_populates="campaign",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name} status={self.status}>"
