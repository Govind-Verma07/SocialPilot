"""
app/schemas/recurring_post.py
-----------------------------
Pydantic v2 schemas for Phase 4: Recurring Posts.
"""

from datetime import datetime, timezone
from typing import Optional, List, Union
from pydantic import BaseModel, Field, model_validator, ConfigDict

from app.schemas.post import AttachedSocialAccount, PostResponse
from app.services.recurrence_service import parse_weekday


class RecurringPostCreate(BaseModel):
    """Payload for creating a new recurring post schedule."""
    content: str = Field(..., description="Post template text/caption")
    social_account_ids: List[str] = Field(..., description="Target social accounts")
    frequency: str = Field(..., description="'daily', 'weekly', or 'monthly'")
    interval: int = Field(1, ge=1, description="Interval step (e.g. every 1 week)")
    start_at: datetime = Field(..., description="Start timestamp in future")
    end_at: datetime = Field(..., description="End boundary timestamp after start_at")
    by_weekday: Optional[Union[int, str]] = Field(None, description="Optional weekday for weekly (0=Monday..6=Sunday or day name)")
    by_month_day: Optional[int] = Field(None, ge=1, le=31, description="Optional day of month for monthly (1..31)")
    occurrence_limit: Optional[int] = Field(None, ge=1, le=200, description="Optional cap on generated occurrences")
    post_type: Optional[str] = Field("text", description="text, image, video, carousel")
    media_urls: Optional[List[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rules(self):
        # 1. Content validation
        if not self.content or not self.content.strip():
            raise ValueError("Post content is required.")
        self.content = self.content.strip()

        # 2. Social accounts validation
        if not self.social_account_ids or len(self.social_account_ids) == 0:
            raise ValueError("Please select at least one social account.")

        # 3. Frequency validation
        freq = (self.frequency or "").strip().lower()
        if freq not in ("daily", "weekly", "monthly"):
            raise ValueError(f"Invalid frequency '{self.frequency}'. Allowed values: daily, weekly, monthly.")
        self.frequency = freq

        # 4. Start date in future
        now = datetime.now(timezone.utc)
        start_utc = self.start_at if self.start_at.tzinfo is not None else self.start_at.replace(tzinfo=timezone.utc)
        if start_utc <= now:
            raise ValueError("Start date/time must be in the future.")
        self.start_at = start_utc

        # 5. End date after start date
        end_utc = self.end_at if self.end_at.tzinfo is not None else self.end_at.replace(tzinfo=timezone.utc)
        if end_utc <= start_utc:
            raise ValueError("End date must be after start date.")
        self.end_at = end_utc

        # 6. Specific frequency validations
        if freq == "weekly" and self.by_weekday is not None:
            # Validate weekday
            parse_weekday(self.by_weekday)

        if freq == "monthly" and self.by_month_day is not None:
            if not (1 <= self.by_month_day <= 31):
                raise ValueError("Monthly recurrence must have a valid day of month (1-31).")

        return self


class RecurringPostUpdate(BaseModel):
    """Payload for updating an existing recurring rule."""
    content: Optional[str] = None
    social_account_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    end_at: Optional[datetime] = None
    post_type: Optional[str] = None
    media_urls: Optional[List[str]] = None


class RecurringRuleResponse(BaseModel):
    """Detailed response representation for a recurring rule."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    content: str
    media_urls: List[str] = []
    post_type: str = "text"
    frequency: str
    interval: int = 1
    by_weekday: Optional[int] = None
    by_month_day: Optional[int] = None
    start_at: datetime
    end_at: datetime
    occurrence_limit: Optional[int] = None
    next_run_at: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    social_accounts: List[AttachedSocialAccount] = []
    generated_count: int = 0
    occurrences: List[PostResponse] = []


class RecurringRuleListResponse(BaseModel):
    """Paginated or listed recurring rules."""
    items: List[RecurringRuleResponse]
    total: int
