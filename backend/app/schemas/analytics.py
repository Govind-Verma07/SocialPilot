"""
app/schemas/analytics.py
------------------------
Pydantic schemas for Milestone 3 Analytics & Reporting engine.
Provides strict type definitions for:
- Post Metric models
- Content Performance Analytics
- Audience & Followers Analytics
- Campaign Performance & ROI Analytics
- Campaign Comparison
- Analytics Export
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Post Metrics
# ---------------------------------------------------------------------------

class PostMetricBase(BaseModel):
    impressions: int = Field(default=0, ge=0)
    reach: int = Field(default=0, ge=0)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    clicks: int = Field(default=0, ge=0)
    video_views: int = Field(default=0, ge=0)
    views: Optional[int] = Field(default=0, ge=0)
    engagement: Optional[int] = Field(default=0, ge=0)
    engagement_rate: Optional[float] = Field(default=0.0, ge=0.0)


class PostMetricCreate(PostMetricBase):
    post_id: str
    social_account_id: Optional[str] = None
    platform: str
    captured_at: Optional[datetime] = None


class PostMetricResponse(PostMetricBase):
    id: str
    post_id: str
    social_account_id: Optional[str] = None
    platform: str
    is_real: bool = True
    captured_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Content Analytics
# ---------------------------------------------------------------------------

class PlatformMetricsSummary(BaseModel):
    platform: str
    post_count: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    impressions: int = 0
    reach: int = 0
    avg_engagement_rate: float = 0.0


class TopPostItem(BaseModel):
    post_id: str
    content: str
    post_type: str
    status: str
    platforms: List[str]
    published_at: Optional[datetime] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    impressions: int = 0
    reach: int = 0
    engagement_rate: float = 0.0
    campaign_id: Optional[str] = None
    campaign_name: Optional[str] = None


class TrendDataPoint(BaseModel):
    date: str  # YYYY-MM-DD
    posts_count: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0
    impressions: int = 0
    reach: int = 0


class ContentAnalyticsOverview(BaseModel):
    total_posts: int = 0
    published_posts: int = 0
    scheduled_posts: int = 0
    draft_posts: int = 0
    failed_posts: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_clicks: int = 0
    total_impressions: int = 0
    total_reach: int = 0
    avg_engagement_rate: float = 0.0


class ContentAnalyticsResponse(BaseModel):
    overview: ContentAnalyticsOverview
    by_platform: List[PlatformMetricsSummary]
    top_posts: List[TopPostItem]
    trend: List[TrendDataPoint]
    time_range: Dict[str, Optional[str]]


# ---------------------------------------------------------------------------
# Audience Analytics
# ---------------------------------------------------------------------------

class AccountAudienceSummary(BaseModel):
    account_id: str
    platform: str
    account_name: str
    account_username: Optional[str] = None
    status: str
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    data_source: str = "social_accounts"
    last_synced_at: Optional[datetime] = None


class AudienceAnalyticsResponse(BaseModel):
    total_connected_accounts: int
    active_accounts: int
    total_followers_tracked: Optional[int] = None
    by_account: List[AccountAudienceSummary]
    by_platform: Dict[str, int]
    unavailable_metrics: List[str] = Field(default_factory=lambda: [
        "demographics (requires enterprise platform API permissions)",
        "follower_growth_history (historical snapshots tracked as accounts sync)",
    ])
    note: str = "Audience metrics represent real data from your authenticated connected social accounts. Demographic breakdowns require partner-level API verification."


# ---------------------------------------------------------------------------
# Campaign Analytics & ROI
# ---------------------------------------------------------------------------

class CampaignMetricsSummary(BaseModel):
    campaign_id: str
    name: str
    status: str
    platform: Optional[str] = None
    objective: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    budget: float = 0.0
    revenue: Optional[float] = None
    conversions: int = 0
    
    # Post execution tracking
    total_posts: int = 0
    published_posts: int = 0
    scheduled_posts: int = 0
    draft_posts: int = 0
    failed_posts: int = 0
    progress_percentage: float = 0.0

    # Engagement & Performance
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    total_clicks: int = 0
    total_impressions: int = 0
    total_reach: int = 0
    total_engagements: int = 0
    avg_engagement_rate: float = 0.0

    # ROI & Performance Ratios
    roi_available: bool = False
    roi_percentage: Optional[float] = None
    cpc: Optional[float] = None  # Cost per click (Budget / Clicks)
    cpa: Optional[float] = None  # Cost per acquisition (Budget / Conversions)
    ctr: Optional[float] = None  # Click-through rate (Clicks / Impressions * 100)
    conversion_rate: Optional[float] = None  # (Conversions / Clicks * 100)


class CampaignAnalyticsResponse(BaseModel):
    overview: Dict[str, Any]
    campaigns: List[CampaignMetricsSummary]


# ---------------------------------------------------------------------------
# Campaign Comparison
# ---------------------------------------------------------------------------

class CampaignComparisonResponse(BaseModel):
    compared_campaigns: List[CampaignMetricsSummary]
    winner_by_engagement: Optional[Dict[str, Any]] = None
    winner_by_roi: Optional[Dict[str, Any]] = None
    comparison_matrix: Dict[str, Dict[str, Any]]


# ---------------------------------------------------------------------------
# Platform Diagnostics & Analytics Sync
# ---------------------------------------------------------------------------

class PlatformDiagnosticItem(BaseModel):
    account_id: str
    platform: str
    display_name: str
    account_name: str
    account_username: Optional[str] = None
    is_connected: bool = True
    has_analytics_permission: bool = True
    last_synced_at: Optional[str] = None
    supported_metrics: List[str] = Field(default_factory=list)
    required_scope: str = ""
    status_message: str = ""


class PlatformDiagnosticsResponse(BaseModel):
    accounts: List[PlatformDiagnosticItem]
    total_accounts: int
    connected_count: int


class AnalyticsSyncResponse(BaseModel):
    user_id: str
    synced_posts_count: int
    metrics_updated_count: int
    accounts_synced: int
    errors: List[str] = Field(default_factory=list)
    synced_at: str

