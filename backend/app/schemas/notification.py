"""
app/schemas/notification.py
----------------------------
Pydantic schemas for the Notification Module (Milestone 4).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChannelPreference(BaseModel):
    """Channel controls for a specific notification type."""
    in_app: bool = True
    email: bool = True


class NotificationPreferencesResponse(BaseModel):
    """Granular user notification preferences."""
    email_notifications: bool
    preferences: Dict[str, ChannelPreference]


class NotificationPreferencesUpdate(BaseModel):
    """Payload to update notification preferences."""
    email_notifications: Optional[bool] = None
    preferences: Optional[Dict[str, ChannelPreference]] = None


class TestEmailRequest(BaseModel):
    """Optional payload for sending an authenticated test email."""
    to_email: Optional[str] = None


class TestEmailResponse(BaseModel):
    """Response returned when triggering test email."""
    success: bool
    message: str
    recipient: str
    smtp_host: str


class NotificationResponse(BaseModel):
    """Full representation of a single notification."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None
    email_status: Optional[str] = None
    email_sent_at: Optional[datetime] = None
    email_error: Optional[str] = None


class NotificationListResponse(BaseModel):
    """Paginated list of notifications."""
    items: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Simple unread notification count response."""
    unread_count: int
