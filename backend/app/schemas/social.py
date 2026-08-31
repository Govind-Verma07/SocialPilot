"""
app/schemas/social.py
---------------------
Pydantic schemas for Social Accounts, Providers, Permissions, and Syncing.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models.enums import AccountStatus, SocialPlatform, SyncStatus


class SocialPlatformInfo(BaseModel):
    platform: SocialPlatform
    display_name: str
    is_configured: bool
    supported_permissions: List[str] = Field(default_factory=list)


class AccountPermissionOut(BaseModel):
    id: str
    social_account_id: str
    permission: str
    granted: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AccountSyncLogOut(BaseModel):
    id: str
    social_account_id: str
    status: SyncStatus
    message: Optional[str] = None
    synced_at: datetime

    model_config = {"from_attributes": True}


class SocialAccountOut(BaseModel):
    id: str
    user_id: str
    team_id: Optional[str] = None
    platform: SocialPlatform
    platform_account_id: str
    account_name: str
    account_username: str
    status: AccountStatus
    connected_at: datetime
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    permissions: List[AccountPermissionOut] = Field(default_factory=list)
    profile_picture_url: Optional[str] = None

    model_config = {"from_attributes": True}


class SocialAuthUrlOut(BaseModel):
    platform: SocialPlatform
    authorization_url: Optional[str] = None
    is_configured: bool
    message: Optional[str] = None


class SyncResponseOut(BaseModel):
    account_id: str
    status: SyncStatus
    message: str
    last_synced_at: datetime
