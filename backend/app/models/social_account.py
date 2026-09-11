"""
app/models/social_account.py
-----------------------------
ORM models for:
  social_accounts     — A user's connected social platform account.
  account_permissions — Fine-grained permissions granted on a social account.
  account_sync_logs   — Immutable history of synchronisation attempts.
"""

import uuid
from datetime import datetime, timezone

# pyrefly: ignore [missing-import]
from sqlalchemy import (
    String, Boolean, DateTime, Text,
    ForeignKey, Enum as SAEnum,
)
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AccountStatus, SocialPlatform, SyncStatus


class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional: accounts can belong to a team
    team_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(
        SAEnum(
            SocialPlatform,
            name="socialplatform",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        index=True,
    )
    # The unique ID for this account on the platform (e.g. Twitter user ID)
    platform_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    account_username: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        SAEnum(
            AccountStatus,
            name="accountstatus",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=AccountStatus.connected.value,
    )
    # Tokens — encrypted at rest by the service layer; NEVER returned to client
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    permissions: Mapped[list["AccountPermission"]] = relationship(
        "AccountPermission", back_populates="account", cascade="all, delete-orphan"
    )
    sync_logs: Mapped[list["AccountSyncLog"]] = relationship(
        "AccountSyncLog", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<SocialAccount id={self.id} platform={self.platform} "
            f"username={self.account_username!r} status={self.status}>"
        )


class AccountPermission(Base):
    __tablename__ = "account_permissions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    social_account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # e.g. "profile_read", "content_publish", "analytics_read"
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    # Relationship
    account: Mapped["SocialAccount"] = relationship(
        "SocialAccount", back_populates="permissions"
    )

    def __repr__(self) -> str:
        return (
            f"<AccountPermission account={self.social_account_id} "
            f"permission={self.permission!r} granted={self.granted}>"
        )


class AccountSyncLog(Base):
    """Immutable log entry per sync attempt (never updated, only inserted)."""
    __tablename__ = "account_sync_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    social_account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(
            SyncStatus,
            name="syncstatus",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    # Human-readable note or error message
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationship
    account: Mapped["SocialAccount"] = relationship(
        "SocialAccount", back_populates="sync_logs"
    )

    def __repr__(self) -> str:
        return (
            f"<AccountSyncLog account={self.social_account_id} "
            f"status={self.status} at={self.synced_at}>"
        )
