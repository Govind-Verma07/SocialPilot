"""
app/models/recurring_rule.py
----------------------------
ORM models for Phase 4: Recurring Posts.
Defines:
  recurring_rules               — Recurring scheduling configuration and content templates.
  recurring_rule_social_accounts — Junction table associating recurring rules with target social accounts.
"""

from typing import TYPE_CHECKING
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, DateTime, JSON, Integer, Boolean,
    ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RecurrenceFrequency

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class RecurringRule(Base):
    """Recurring post rule that defines frequency, schedule boundaries, and content template."""
    __tablename__ = "recurring_rules"

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
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    post_type: Mapped[str] = mapped_column(String(50), nullable=False, default="text")

    frequency: Mapped[str] = mapped_column(
        SAEnum(
            RecurrenceFrequency,
            name="recurrencefrequency",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    by_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=Monday .. 6=Sunday
    by_month_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..31

    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    occurrence_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

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
    user = relationship("User", foreign_keys=[user_id])
    social_accounts: Mapped[list["RecurringRuleSocialAccount"]] = relationship(
        "RecurringRuleSocialAccount",
        back_populates="recurring_rule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="recurring_rule",
        cascade="all, delete-orphan",
    )


class RecurringRuleSocialAccount(Base):
    """Junction table associating a RecurringRule with one or more target SocialAccounts."""
    __tablename__ = "recurring_rule_social_accounts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    recurring_rule_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recurring_rules.id", ondelete="CASCADE"),
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
    recurring_rule: Mapped["RecurringRule"] = relationship("RecurringRule", back_populates="social_accounts")
    social_account = relationship("SocialAccount", lazy="joined")
