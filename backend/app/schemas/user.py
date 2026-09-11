"""
app/schemas/user.py
-------------------
Pydantic schemas for user profile and user settings management.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole


class UserUpdate(BaseModel):
    """Payload for updating user profile. Role, email, and is_active are non-editable here."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=150, examples=["Jane Doe"])


class UserSettingsOut(BaseModel):
    """User settings response."""
    id: str
    user_id: str
    email_notifications: bool
    timezone: str
    extra: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserSettingsUpdate(BaseModel):
    """Payload for updating user preferences."""
    email_notifications: Optional[bool] = None
    timezone: Optional[str] = Field(None, max_length=50, examples=["UTC", "America/New_York"])
    extra: Optional[str] = None
