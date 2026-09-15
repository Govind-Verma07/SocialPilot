"""
app/models/enums.py
-------------------
Shared Python enumerations used across ORM models.

These enums are the single source of truth for:
  - UserRole         — valid values for users.role
  - AccountStatus    — valid states for a connected social account
  - SyncStatus       — result states for a sync attempt
  - SocialPlatform   — supported social platforms
"""

import enum


class UserRole(str, enum.Enum):
    """Roles available in the SocialPilot RBAC system."""
    content_creator = "content_creator"
    marketing_team  = "marketing_team"
    business_user   = "business_user"
    administrator   = "administrator"


class SocialPlatform(str, enum.Enum):
    """Supported social media platforms."""
    facebook  = "facebook"
    instagram = "instagram"
    linkedin  = "linkedin"
    x         = "x"
    youtube   = "youtube"
    pinterest = "pinterest"


class AccountStatus(str, enum.Enum):
    """Connection/health status of a social account."""
    connected     = "connected"
    disconnected  = "disconnected"
    pending       = "pending"
    error         = "error"
    token_expired = "token_expired"


class SyncStatus(str, enum.Enum):
    """Result of the most recent synchronization attempt."""
    success = "success"
    failed  = "failed"
    pending = "pending"


class TeamMemberRole(str, enum.Enum):
    """Role a user can hold within a team."""
    owner  = "owner"
    admin  = "admin"
    member = "member"
    viewer = "viewer"


class PostStatus(str, enum.Enum):
    """Lifecycle status of a social media post."""
    draft      = "draft"
    scheduled  = "scheduled"
    publishing = "publishing"
    published  = "published"
    failed     = "failed"



class RecurrenceFrequency(str, enum.Enum):
    """Frequency intervals for recurring post rules."""
    daily   = "daily"
    weekly  = "weekly"
    monthly = "monthly"


class PublishingJobStatus(str, enum.Enum):
    """Lifecycle status of a platform publishing job in the queue (Phase 8)."""
    queued     = "queued"
    processing = "processing"
    published  = "published"
    retrying   = "retrying"
    failed     = "failed"
    cancelled  = "cancelled"
    skipped    = "skipped"


class PublishingLogEventType(str, enum.Enum):
    """Event types recorded during publishing lifecycle (Phase 9)."""
    queued              = "QUEUED"
    processing          = "PROCESSING"
    publishing_started  = "PUBLISHING_STARTED"
    published           = "PUBLISHED"
    retrying            = "RETRYING"
    failed              = "FAILED"
    cancelled           = "CANCELLED"
    skipped             = "SKIPPED"




