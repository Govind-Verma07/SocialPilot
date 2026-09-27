"""
app/api/v1/endpoints/campaigns.py
---------------------------------
REST API endpoints for Milestone 3: Campaign Management & Performance Tracking.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.models.user import User
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
    CampaignAttachPostsRequest,
)
from app.schemas.post import PostResponse, PostListResponse
from app.services.campaign_service import CampaignService
from app.api.v1.endpoints.posts import _serialize_post

router = APIRouter()


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_campaign(
    payload: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new marketing campaign."""
    campaign = CampaignService.create_campaign(db, current_user.id, payload)
    tracking = CampaignService.calculate_tracking_stats(db, campaign)
    resp = CampaignResponse.model_validate(campaign)
    resp.tracking = tracking
    resp.tracking_stats = tracking
    return resp


@router.get("", response_model=CampaignListResponse)
@router.get("/", response_model=CampaignListResponse, include_in_schema=False)
def list_campaigns(
    status: Optional[str] = Query(None, description="Filter by status (active, scheduled, completed, paused, draft)"),
    platform: Optional[str] = Query(None, description="Filter by target platform"),
    search: Optional[str] = Query(None, description="Search term across name and description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List authenticated user's campaigns with filters, pagination, and real tracking statistics."""
    skip = (page - 1) * page_size
    campaigns, total = CampaignService.list_campaigns(
        db, current_user.id, status, platform, search, skip, page_size
    )

    items = []
    for c in campaigns:
        tracking = CampaignService.calculate_tracking_stats(db, c)
        c_resp = CampaignResponse.model_validate(c)
        c_resp.tracking = tracking
        c_resp.tracking_stats = tracking
        items.append(c_resp)

    return CampaignListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details and real tracking metrics for a single campaign."""
    campaign = CampaignService.get_campaign_or_404(db, campaign_id, current_user.id)
    tracking = CampaignService.calculate_tracking_stats(db, campaign)
    resp = CampaignResponse.model_validate(campaign)
    resp.tracking = tracking
    resp.tracking_stats = tracking
    return resp


@router.put("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: str,
    payload: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a campaign's attributes, timeframe, or budget."""
    campaign = CampaignService.update_campaign(db, campaign_id, current_user.id, payload)
    tracking = CampaignService.calculate_tracking_stats(db, campaign)
    resp = CampaignResponse.model_validate(campaign)
    resp.tracking = tracking
    resp.tracking_stats = tracking
    return resp


@router.delete("/{campaign_id}", status_code=status.HTTP_200_OK)
def delete_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a campaign and safely dissociate its posts."""
    CampaignService.delete_campaign(db, campaign_id, current_user.id)
    return {"message": "Campaign successfully deleted", "id": campaign_id}


@router.post("/{campaign_id}/posts", status_code=status.HTTP_200_OK)
def attach_posts_to_campaign(
    campaign_id: str,
    payload: CampaignAttachPostsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Associate existing scheduled or published posts to this campaign."""
    posts = CampaignService.attach_posts(db, campaign_id, current_user.id, payload.post_ids)
    return {
        "message": f"Successfully attached {len(posts)} post(s) to campaign",
        "campaign_id": campaign_id,
        "attached_post_ids": [p.id for p in posts],
    }


@router.delete("/{campaign_id}/posts/{post_id}", status_code=status.HTTP_200_OK)
def remove_post_from_campaign(
    campaign_id: str,
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a post from this campaign (preserves the post itself)."""
    CampaignService.detach_post(db, campaign_id, post_id, current_user.id)
    return {
        "message": f"Post '{post_id}' dissociated from campaign '{campaign_id}'",
        "campaign_id": campaign_id,
        "post_id": post_id,
    }


@router.get("/{campaign_id}/posts", response_model=PostListResponse)
def get_campaign_posts(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve all posts associated with this campaign."""
    posts = CampaignService.get_campaign_posts(db, campaign_id, current_user.id)
    return PostListResponse(
        items=[PostResponse(**_serialize_post(p)) for p in posts],
        total=len(posts),
    )
