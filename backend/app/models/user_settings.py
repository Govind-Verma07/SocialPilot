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

    def get_notification_preferences(self) -> dict:
        """
        Return parsed notification preferences dictionary.
        Format:
        {
            "post_published": {"in_app": True, "email": True},
            "post_failed": {"in_app": True, "email": True},
            "post_scheduled": {"in_app": True, "email": True},
            "scheduled_reminder": {"in_app": True, "email": True},
            "campaign_event": {"in_app": True, "email": True},
            "account_issue": {"in_app": True, "email": True},
            "system_alert": {"in_app": True, "email": True},
        }
        """
        import json
        defaults = {
            "post_published": {"in_app": True, "email": bool(self.email_notifications)},
            "post_failed": {"in_app": True, "email": bool(self.email_notifications)},
            "post_scheduled": {"in_app": True, "email": bool(self.email_notifications)},
            "scheduled_reminder": {"in_app": True, "email": bool(self.email_notifications)},
            "campaign_event": {"in_app": True, "email": bool(self.email_notifications)},
            "account_issue": {"in_app": True, "email": bool(self.email_notifications)},
            "system_alert": {"in_app": True, "email": bool(self.email_notifications)},
        }
        if not self.extra:
            return defaults
        try:
            extra_dict = json.loads(self.extra)
            stored_prefs = extra_dict.get("notification_preferences", {})
            for key, def_val in defaults.items():
                if key in stored_prefs and isinstance(stored_prefs[key], dict):
                    defaults[key] = {
                        "in_app": bool(stored_prefs[key].get("in_app", def_val["in_app"])),
                        "email": bool(stored_prefs[key].get("email", def_val["email"])),
                    }
        except Exception:
            pass
        return defaults

    def set_notification_preferences(self, prefs: dict):
        """Update notification preferences stored inside JSON `extra` field."""
        import json
        extra_dict = {}
        if self.extra:
            try:
                extra_dict = json.loads(self.extra)
            except Exception:
                extra_dict = {}
        extra_dict["notification_preferences"] = prefs
        self.extra = json.dumps(extra_dict)

    def is_channel_enabled(self, event_type: str, channel: str) -> bool:
        """
        Check if a given channel ('in_app' or 'email') is enabled for an event type.
        Channel: 'in_app' | 'email'
        Event type: 'post_published', 'post_failed', 'post_scheduled', 'scheduled_reminder',
                    'campaign_created', 'campaign_updated', 'campaign_completed', 'account_issue', 'system_alert'
        """
        if channel == "email" and not self.email_notifications:
            return False

        # Normalize event type aliases
        norm_type = event_type
        if event_type in ("campaign_created", "campaign_updated", "campaign_completed"):
            norm_type = "campaign_event"

        prefs = self.get_notification_preferences()
        type_prefs = prefs.get(norm_type, {"in_app": True, "email": True})
        return bool(type_prefs.get(channel, True))

    def __repr__(self) -> str:
        return f"<UserSettings user={self.user_id}>"

