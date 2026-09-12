"""
app/schemas/post.py
-------------------
Pydantic v2 schemas for Post Scheduling & Draft Lifecycle.
"""

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator, ConfigDict


class AttachedSocialAccount(BaseModel):
    """Summary of a social account attached to a post."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: str
    account_name: str
    account_username: str
    status: Optional[str] = None


class PostCreate(BaseModel):
    """Payload for creating a post (either scheduled or draft)."""
    content: Optional[str] = Field("", description="Post text/caption")
    social_account_ids: Optional[List[str]] = Field(default_factory=list, description="Target social accounts")
    scheduled_at: Optional[datetime] = Field(None, description="Future timestamp when the post should be published")
    status: Optional[str] = Field("scheduled", description="draft or scheduled")
    post_type: Optional[str] = Field("text", description="Format: text, image, video, carousel, story, reel")
    media_urls: Optional[List[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lifecycle_rules(self):
        post_status = (self.status or "scheduled").lower()

        if post_status == "scheduled":
            # 1. Content validation
            if not self.content or not self.content.strip():
                raise ValueError("Post content is required.")
            self.content = self.content.strip()

            # 2. Social accounts validation
            if not self.social_account_ids or len(self.social_account_ids) == 0:
                raise ValueError("Please select at least one social account.")

            # 3. Future scheduled date validation
            if not self.scheduled_at:
                raise ValueError("Scheduled time is required for scheduled posts.")
            now = datetime.now(timezone.utc)
            target = self.scheduled_at if self.scheduled_at.tzinfo is not None else self.scheduled_at.replace(tzinfo=timezone.utc)
            if target <= now:
                raise ValueError("Scheduled time must be in the future.")
            self.scheduled_at = target
        elif post_status == "draft":
            # Strip content if present, allow empty string
            if self.content:
                self.content = self.content.strip()

        return self


class PostUpdate(BaseModel):
    """Payload for updating an existing post or draft."""
    content: Optional[str] = None
    social_account_ids: Optional[List[str]] = None
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None
    post_type: Optional[str] = None
    media_urls: Optional[List[str]] = None


class PublishResultResponse(BaseModel):
    """Result of a publishing attempt on a specific social account/platform."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    post_id: str
    social_account_id: Optional[str] = None
    platform: str
    status: str  # "published" or "failed"
    platform_post_id: Optional[str] = None
    published_url: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None
    created_at: datetime


class PublishingJobResponse(BaseModel):
    """Status of an asynchronous publishing job in the queue (Phase 8)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    post_id: str
    social_account_id: str
    platform: Optional[str] = None
    status: str
    attempt_count: int = 0
    max_attempts: int = 3
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PublishingLogResponse(BaseModel):
    """Publishing log entry for tracking events, retries, and errors (Phase 9)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    post_id: str
    publishing_job_id: Optional[str] = None
    social_account_id: Optional[str] = None
    platform: str
    event_type: str
    status: str
    attempt_number: int = 1
    platform_post_id: Optional[str] = None
    published_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


class PublishingLogListResponse(BaseModel):
    """Paginated list of publishing logs."""
    items: List[PublishingLogResponse]
    total: int
    page: int = 1
    limit: int = 50


class PostResponse(BaseModel):
    """Response returned when a post is created, updated, or fetched."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    team_id: Optional[str] = None
    content: str
    media_urls: Optional[List[str]] = []
    post_type: str = "text"
    status: str
    scheduled_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    recurring_rule_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    social_accounts: List[AttachedSocialAccount] = []
    publish_results: List[PublishResultResponse] = []
    publishing_jobs: List[PublishingJobResponse] = []


class PostListResponse(BaseModel):
    """Paginated list of posts."""
    items: List[PostResponse]
    total: int
