"""
app/api/v1/endpoints/analytics.py
---------------------------------
Endpoints for Milestone 3 Analytics & Reporting engine.
Provides:
- GET  /analytics/content     — Content performance, platform breakdowns, top posts, trends
- GET  /analytics/audience    — Connected accounts audience & follower stats
- GET  /analytics/campaigns   — Campaign metrics, progress, and ROI analytics
- POST /analytics/comparison  — Side-by-side campaign comparison
- GET  /analytics/export      — CSV / JSON report export
- POST /analytics/metrics     — Record or update post metrics
"""

from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.post import Post
from app.models.analytics import PostMetric
from app.services.auth_service import get_current_user
from app.services.analytics_service import AnalyticsService
from app.services.social_analytics_service import SocialAnalyticsService
from app.schemas.analytics import (
    ContentAnalyticsResponse,
    AudienceAnalyticsResponse,
    CampaignAnalyticsResponse,
    CampaignComparisonResponse,
    PostMetricCreate,
    PostMetricResponse,
    PlatformDiagnosticItem,
    PlatformDiagnosticsResponse,
    AnalyticsSyncResponse,
)

router = APIRouter()


def _parse_filter_date(dt_str: Optional[str], is_end: bool = False) -> Optional[datetime]:
    if not dt_str:
        return None
    clean_str = dt_str.strip().replace(" ", "+").replace("Z", "+00:00")
    if len(clean_str) == 10 and clean_str.count("-") == 2:
        d = datetime.strptime(clean_str, "%Y-%m-%d")
        if is_end:
            return d.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc)
        return d.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format for '{dt_str}'. Use YYYY-MM-DD or ISO 8601.",
        )


class CampaignCompareRequest(BaseModel):
    campaign_ids: List[str] = Field(..., min_length=1, max_length=10)


@router.get("/content", response_model=ContentAnalyticsResponse, status_code=status.HTTP_200_OK)
def get_content_analytics(
    platform: Optional[str] = Query(None, description="Filter by social platform (e.g. twitter, instagram)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or ISO 8601)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or ISO 8601)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContentAnalyticsResponse:
    """
    Retrieve real aggregated content analytics for the authenticated user,
    including overview counts, platform breakdown, top posts, and trend history.
    """
    parsed_start = _parse_filter_date(start_date, is_end=False)
    parsed_end = _parse_filter_date(end_date, is_end=True)

    return AnalyticsService.get_content_analytics(
        db=db,
        user_id=current_user.id,
        platform=platform,
        start_date=parsed_start,
        end_date=parsed_end,
    )


@router.get("/audience", response_model=AudienceAnalyticsResponse, status_code=status.HTTP_200_OK)
def get_audience_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AudienceAnalyticsResponse:
    """
    Retrieve audience and follower metrics across connected accounts.
    Explicitly clarifies metric boundaries where platform APIs restrict demographic metrics.
    """
    return AnalyticsService.get_audience_analytics(
        db=db,
        user_id=current_user.id,
    )


@router.get("/campaigns", response_model=CampaignAnalyticsResponse, status_code=status.HTTP_200_OK)
def get_campaign_analytics(
    campaign_id: Optional[str] = Query(None, description="Filter to a specific campaign ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignAnalyticsResponse:
    """
    Retrieve campaign performance metrics, post execution tracking, and honest ROI analytics.
    """
    return AnalyticsService.get_campaign_analytics(
        db=db,
        user_id=current_user.id,
        campaign_id=campaign_id,
    )


@router.post("/comparison", response_model=CampaignComparisonResponse, status_code=status.HTTP_200_OK)
def compare_campaigns(
    payload: CampaignCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CampaignComparisonResponse:
    """
    Perform a side-by-side comparison between 2 or more campaigns.
    """
    return AnalyticsService.compare_campaigns(
        db=db,
        user_id=current_user.id,
        campaign_ids=payload.campaign_ids,
    )


@router.get("/export", status_code=status.HTTP_200_OK)
def export_analytics(
    export_format: str = Query("csv", alias="format", pattern="^(csv|json)$"),
    export_type: str = Query("all", pattern="^(all|posts|campaigns)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Export analytics data as downloadable CSV or JSON.
    """
    if export_format == "csv":
        csv_content = AnalyticsService.export_analytics_csv(
            db=db,
            user_id=current_user.id,
            export_type=export_type,
        )
        filename = f"socialpilot_analytics_{export_type}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )
    else:
        content_data = AnalyticsService.get_content_analytics(db=db, user_id=current_user.id)
        campaign_data = AnalyticsService.get_campaign_analytics(db=db, user_id=current_user.id)
        return {
            "content": content_data.model_dump(),
            "campaigns": campaign_data.model_dump(),
        }


@router.post("/metrics", response_model=PostMetricResponse, status_code=status.HTTP_201_CREATED)
def record_post_metric(
    payload: PostMetricCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PostMetricResponse:
    """
    Record or update real performance metrics for a published post.
    Verifies that the target post belongs to the authenticated user.
    """
    post = db.query(Post).filter(Post.id == payload.post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found.",
        )
    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this post.",
        )

    # Check if a metric row already exists for post + social_account
    existing = None
    if payload.social_account_id:
        existing = db.query(PostMetric).filter(
            PostMetric.post_id == payload.post_id,
            PostMetric.social_account_id == payload.social_account_id,
        ).first()
    else:
        existing = db.query(PostMetric).filter(
            PostMetric.post_id == payload.post_id,
            PostMetric.platform == payload.platform,
        ).first()

    now = datetime.now(timezone.utc)
    total_eng = (payload.likes or 0) + (payload.comments or 0) + (payload.shares or 0) + (payload.clicks or 0)
    video_v = payload.video_views if payload.video_views else (payload.views or 0)

    if existing:
        existing.impressions = payload.impressions
        existing.reach = payload.reach
        existing.likes = payload.likes
        existing.comments = payload.comments
        existing.shares = payload.shares
        existing.clicks = payload.clicks
        existing.video_views = video_v
        existing.engagement = payload.engagement if payload.engagement else total_eng
        existing.captured_at = payload.captured_at or now
        db.commit()
        db.refresh(existing)
        return PostMetricResponse.model_validate(existing)

    metric = PostMetric(
        post_id=payload.post_id,
        social_account_id=payload.social_account_id,
        platform=payload.platform,
        impressions=payload.impressions,
        reach=payload.reach,
        likes=payload.likes,
        comments=payload.comments,
        shares=payload.shares,
        clicks=payload.clicks,
        video_views=video_v,
        engagement=payload.engagement if payload.engagement else total_eng,
        is_real=True,
        captured_at=payload.captured_at or now,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return PostMetricResponse.model_validate(metric)


@router.post("/sync", response_model=AnalyticsSyncResponse, status_code=status.HTTP_200_OK)
async def sync_social_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of days in the past to sync metrics for published posts"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalyticsSyncResponse:
    """
    On-demand synchronization of real platform performance metrics for the authenticated user.
    Queries official platform APIs (LinkedIn, Facebook, Instagram, YouTube, X, Pinterest)
    using stored platform post IDs and decrypted OAuth access tokens.
    """
    res = await SocialAnalyticsService.sync_user_analytics(
        db=db,
        user_id=current_user.id,
        days=days,
    )
    return AnalyticsSyncResponse(**res)


@router.get("/diagnostics", response_model=PlatformDiagnosticsResponse, status_code=status.HTTP_200_OK)
def get_analytics_diagnostics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlatformDiagnosticsResponse:
    """
    Retrieve diagnostic connection and permission status for all connected social platforms.
    Enables users to identify missing scopes or disconnected accounts preventing metrics retrieval.
    """
    diag_list = SocialAnalyticsService.get_platform_diagnostics(db=db, user_id=current_user.id)
    connected_cnt = sum(1 for d in diag_list if d["is_connected"])
    return PlatformDiagnosticsResponse(
        accounts=[PlatformDiagnosticItem(**d) for d in diag_list],
        total_accounts=len(diag_list),
        connected_count=connected_cnt,
    )

