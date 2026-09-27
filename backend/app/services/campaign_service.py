"""
app/services/campaign_service.py
--------------------------------
Service layer for Milestone 3: Campaign Management, Post Associations & Performance Tracking.
Applies user isolation and ownership checks across all campaign operations.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_
from fastapi import HTTPException, status

from app.models.campaign import Campaign
from app.models.post import Post, PostSocialAccount
from app.models.post_publish_result import PostPublishResult
from app.models.analytics import PostMetric
from app.models.enums import PostStatus
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignTrackingStats


class CampaignService:
    @staticmethod
    def get_campaign_or_404(db: Session, campaign_id: str, user_id: str) -> Campaign:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Campaign with ID '{campaign_id}' not found",
            )
        if campaign.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access or modify this campaign",
            )
        return campaign

    @staticmethod
    def calculate_tracking_stats(db: Session, campaign: Campaign) -> CampaignTrackingStats:
        """Calculate real post counts, platform breakdown, metrics, and progress for a campaign."""
        posts = db.query(Post).filter(Post.campaign_id == campaign.id).all()
        total_posts = len(posts)

        scheduled_posts = sum(1 for p in posts if p.status == PostStatus.scheduled.value)
        published_posts = sum(1 for p in posts if p.status == PostStatus.published.value)
        failed_posts = sum(1 for p in posts if p.status == PostStatus.failed.value)
        draft_posts = sum(1 for p in posts if p.status == PostStatus.draft.value)

        # Progress %: published vs actionable posts (scheduled + published)
        actionable = scheduled_posts + published_posts
        progress_pct = (published_posts / actionable * 100.0) if actionable > 0 else (100.0 if published_posts > 0 else 0.0)

        # Platform distribution
        post_ids = [p.id for p in posts]
        platform_breakdown: Dict[str, int] = {}
        if post_ids:
            # Query junction table PostSocialAccount join SocialAccount
            psa_links = (
                db.query(PostSocialAccount)
                .filter(PostSocialAccount.post_id.in_(post_ids))
                .all()
            )
            for link in psa_links:
                if link.social_account and link.social_account.platform:
                    plat = link.social_account.platform.lower()
                    platform_breakdown[plat] = platform_breakdown.get(plat, 0) + 1

        # Real Metrics aggregation from PostMetric
        real_metrics = {
            "engagement": 0,
            "reach": 0,
            "impressions": 0,
            "clicks": 0,
        }
        if post_ids:
            metrics = db.query(PostMetric).filter(PostMetric.post_id.in_(post_ids)).all()
            for m in metrics:
                real_metrics["engagement"] += m.engagement
                real_metrics["reach"] += m.reach
                real_metrics["impressions"] += m.impressions
                real_metrics["clicks"] += m.clicks

        # ROI calculation (strictly using real revenue & budget)
        roi_percentage: Optional[float] = None
        roi_available = False
        roi_message = "ROI tracking requires revenue or conversion value data."

        budget_val = float(campaign.budget or 0.0)
        if campaign.revenue is not None and budget_val > 0:
            rev_val = float(campaign.revenue)
            roi_percentage = round(((rev_val - budget_val) / budget_val) * 100.0, 2)
            roi_available = True
            roi_message = f"ROI calculated from verified revenue (${rev_val:,.2f}) vs budget (${budget_val:,.2f})"
        elif campaign.revenue is not None and budget_val == 0:
            roi_percentage = 100.0
            roi_available = True
            roi_message = "Positive ROI (Zero spend)"

        return CampaignTrackingStats(
            total_posts=total_posts,
            scheduled_posts=scheduled_posts,
            published_posts=published_posts,
            failed_posts=failed_posts,
            draft_posts=draft_posts,
            progress_percentage=round(progress_pct, 1),
            platform_breakdown=platform_breakdown,
            total_budget=budget_val,
            real_engagement=real_metrics["engagement"],
            real_reach=real_metrics["reach"],
            real_impressions=real_metrics["impressions"],
            real_clicks=real_metrics["clicks"],
            roi_percentage=roi_percentage,
            roi_available=roi_available,
            roi_message=roi_message,
        )

    @classmethod
    def create_campaign(cls, db: Session, user_id: str, payload: CampaignCreate) -> Campaign:
        campaign = Campaign(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            platform=payload.platform,
            start_date=payload.start_date,
            end_date=payload.end_date,
            budget=payload.budget,
            revenue=payload.revenue,
            conversions=payload.conversions,
            objective=payload.objective,
            status=payload.status,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        # Attach initial posts if supplied
        if payload.post_ids:
            cls.attach_posts(db, campaign.id, user_id, payload.post_ids)

        # Notification: campaign created
        try:
            from app.services.notification_service import create_campaign_notification
            create_campaign_notification(db, user_id, campaign.id, campaign.name, "created")
        except Exception:
            pass

        return campaign

    @classmethod
    def list_campaigns(
        cls,
        db: Session,
        user_id: str,
        status_filter: Optional[str] = None,
        platform_filter: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[Campaign], int]:
        query = db.query(Campaign).filter(Campaign.user_id == user_id)

        if status_filter and status_filter.lower() != "all":
            query = query.filter(Campaign.status == status_filter.lower())

        if platform_filter and platform_filter.lower() != "all":
            query = query.filter(Campaign.platform.ilike(f"%{platform_filter}%"))

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Campaign.name.ilike(search_pattern),
                    Campaign.description.ilike(search_pattern),
                    Campaign.objective.ilike(search_pattern),
                )
            )

        total = query.count()
        campaigns = query.order_by(desc(Campaign.created_at)).offset(skip).limit(limit).all()
        return campaigns, total

    @classmethod
    def update_campaign(cls, db: Session, campaign_id: str, user_id: str, payload: CampaignUpdate) -> Campaign:
        campaign = cls.get_campaign_or_404(db, campaign_id, user_id)

        update_data = payload.model_dump(exclude_unset=True)
        # Validate date ordering if either is modified
        start = update_data.get("start_date", campaign.start_date)
        end = update_data.get("end_date", campaign.end_date)
        if start and end and end < start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end_date cannot logically precede start_date",
            )

        for key, value in update_data.items():
            setattr(campaign, key, value)

        campaign.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(campaign)

        # Notification: campaign updated / completed
        try:
            from app.services.notification_service import create_campaign_notification
            event_type = "completed" if campaign.status == "completed" else "updated"
            create_campaign_notification(db, user_id, campaign.id, campaign.name, event_type)
        except Exception:
            pass

        return campaign

    @classmethod
    def delete_campaign(cls, db: Session, campaign_id: str, user_id: str) -> None:
        campaign = cls.get_campaign_or_404(db, campaign_id, user_id)
        # Dissociate posts first (sets campaign_id = None)
        db.query(Post).filter(Post.campaign_id == campaign.id).update({"campaign_id": None})
        db.delete(campaign)
        db.commit()

    @classmethod
    def attach_posts(cls, db: Session, campaign_id: str, user_id: str, post_ids: List[str]) -> List[Post]:
        campaign = cls.get_campaign_or_404(db, campaign_id, user_id)

        posts = db.query(Post).filter(Post.id.in_(post_ids)).all()
        if len(posts) != len(post_ids):
            found_ids = {p.id for p in posts}
            missing = set(post_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Posts not found: {list(missing)}",
            )

        # Enforce user ownership on all posts
        for post in posts:
            if post.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"You do not own post '{post.id}' and cannot attach it to your campaign",
                )
            post.campaign_id = campaign.id

        db.commit()
        return posts

    @classmethod
    def detach_post(cls, db: Session, campaign_id: str, post_id: str, user_id: str) -> None:
        cls.get_campaign_or_404(db, campaign_id, user_id)
        post = db.query(Post).filter(Post.id == post_id, Post.campaign_id == campaign_id).first()
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Post '{post_id}' is not associated with campaign '{campaign_id}'",
            )
        if post.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        post.campaign_id = None
        db.commit()

    @classmethod
    def get_campaign_posts(cls, db: Session, campaign_id: str, user_id: str) -> List[Post]:
        cls.get_campaign_or_404(db, campaign_id, user_id)
        return db.query(Post).filter(Post.campaign_id == campaign_id).order_by(desc(Post.created_at)).all()
