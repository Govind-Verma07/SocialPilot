"""
app/schemas/campaign.py
-----------------------
Pydantic validation schemas for Milestone 3: Campaign Management & Performance Tracking.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Campaign title")
    description: Optional[str] = Field(None, max_length=2000, description="Campaign details and notes")
    platform: str = Field("multi", max_length=100, description="Target platform (facebook, instagram, linkedin, x, youtube, pinterest, or multi)")
    start_date: Optional[datetime] = Field(None, description="Campaign kickoff timestamp")
    end_date: Optional[datetime] = Field(None, description="Campaign conclusion timestamp")
    budget: float = Field(0.0, ge=0.0, description="Total allocated budget in USD")
    revenue: Optional[float] = Field(None, ge=0.0, description="Total realized revenue in USD")
    conversions: int = Field(0, ge=0, description="Number of tracked goal conversions")
    objective: str = Field("Brand Awareness", max_length=100, description="Campaign goal")
    status: str = Field("active", max_length=50, description="Status: active, scheduled, completed, paused, draft")

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: Optional[datetime], info) -> Optional[datetime]:
        start = info.data.get("start_date")
        if start and v and v < start:
            raise ValueError("end_date cannot logically precede start_date")
        return v


class CampaignCreate(CampaignBase):
    post_ids: Optional[List[str]] = Field(default_factory=list, description="Optional post IDs to associate on creation")


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    platform: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: Optional[float] = Field(None, ge=0.0)
    revenue: Optional[float] = Field(None, ge=0.0)
    conversions: Optional[int] = Field(None, ge=0)
    objective: Optional[str] = None
    status: Optional[str] = None

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: Optional[datetime], info) -> Optional[datetime]:
        start = info.data.get("start_date")
        if start and v and v < start:
            raise ValueError("end_date cannot logically precede start_date")
        return v


class CampaignTrackingStats(BaseModel):
    total_posts: int = 0
    scheduled_posts: int = 0
    published_posts: int = 0
    failed_posts: int = 0
    draft_posts: int = 0
    progress_percentage: float = 0.0
    platform_breakdown: Dict[str, int] = Field(default_factory=dict)
    total_budget: float = 0.0
    real_engagement: int = 0
    real_reach: int = 0
    real_impressions: int = 0
    real_clicks: int = 0
    roi_percentage: Optional[float] = None
    roi_available: bool = False
    roi_message: Optional[str] = None


class CampaignResponse(CampaignBase):
    id: str
    user_id: str
    team_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tracking: Optional[CampaignTrackingStats] = None
    tracking_stats: Optional[CampaignTrackingStats] = None

    class Config:
        from_attributes = True


class CampaignListResponse(BaseModel):
    items: List[CampaignResponse]
    total: int
    page: int = 1
    page_size: int = 50


class CampaignAttachPostsRequest(BaseModel):
    post_ids: List[str] = Field(..., min_length=1, description="List of post UUIDs to attach to this campaign")
