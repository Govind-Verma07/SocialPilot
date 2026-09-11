"""
app/models/user_settings.py
----------------------------
ORM model for the `user_settings` table.

One row per user; stores lightweight preference flags.
Extensible — add columns via Alembic migrations in future milestones.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # one row per user
        index=True,
    )
    # ── Notification preferences (placeholder for Milestone 4) ──────────
    email_notifications: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # ── UI preferences ──────────────────────────────────────────────────
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="UTC"
    )
    # JSON-encoded extra preferences — avoids schema churn for minor flags
    extra: Mapped[str | None] = mapped_column(Text, nullable=True)

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

    def __repr__(self) -> str:
        return f"<UserSettings user={self.user_id}>"
