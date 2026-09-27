"""
app/services/analytics_service.py
---------------------------------
Business logic and aggregation engine for Milestone 3 Analytics.
Handles:
- Content Performance Analytics
- Audience & Connected Accounts Analytics
- Campaign Performance & Honest ROI Calculations
- Multi-Campaign Comparison
- CSV Export Generation
"""

import csv
import io
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_

from app.models.campaign import Campaign
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.models.analytics import PostMetric
from app.models.enums import PostStatus
from app.schemas.analytics import (
    ContentAnalyticsResponse,
    ContentAnalyticsOverview,
    PlatformMetricsSummary,
    TopPostItem,
    TrendDataPoint,
    AudienceAnalyticsResponse,
    AccountAudienceSummary,
    CampaignAnalyticsResponse,
    CampaignMetricsSummary,
    CampaignComparisonResponse,
)


class AnalyticsService:

    @staticmethod
    def get_content_analytics(
        db: Session,
        user_id: str,
        platform: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ContentAnalyticsResponse:
        """
        Calculate aggregated content metrics for the user's posts,
        including platform breakdown, top posts, and daily trend.
        """
        query = db.query(Post).options(
            joinedload(Post.social_accounts).joinedload(PostSocialAccount.social_account),
            joinedload(Post.metrics),
            joinedload(Post.campaign),
        ).filter(Post.user_id == user_id)

        if start_date:
            query = query.filter(
                or_(
                    Post.published_at >= start_date,
                    and_(Post.published_at.is_(None), Post.created_at >= start_date),
                )
            )

        if end_date:
            query = query.filter(
                or_(
                    Post.published_at <= end_date,
                    and_(Post.published_at.is_(None), Post.created_at <= end_date),
                )
            )

        posts = query.all()

        # Filter by platform if specified
        if platform:
            norm_plat = platform.strip().lower()
            filtered_posts = []
            for p in posts:
                platforms = [
                    (psa.social_account.platform.value if hasattr(psa.social_account.platform, "value") else str(psa.social_account.platform)).lower()
                    for psa in p.social_accounts
                    if psa.social_account
                ]
                if norm_plat in platforms:
                    filtered_posts.append(p)
            posts = filtered_posts

        # Initialize counters
        total_posts = len(posts)
        published_posts = 0
        scheduled_posts = 0
        draft_posts = 0
        failed_posts = 0

        total_likes = 0
        total_comments = 0
        total_shares = 0
        total_clicks = 0
        total_impressions = 0
        total_reach = 0
        engagement_rates = []

        platform_agg: Dict[str, Dict[str, Any]] = {}
        daily_agg: Dict[str, Dict[str, int]] = {}
        top_post_items: List[TopPostItem] = []

        for post in posts:
            status_str = post.status.value if hasattr(post.status, "value") else str(post.status).lower()
            if status_str == PostStatus.published.value:
                published_posts += 1
            elif status_str == PostStatus.scheduled.value:
                scheduled_posts += 1
            elif status_str == PostStatus.draft.value:
                draft_posts += 1
            elif status_str == PostStatus.failed.value:
                failed_posts += 1

            # Determine post platforms
            post_platforms = []
            for psa in post.social_accounts:
                if psa.social_account:
                    plat_val = psa.social_account.platform.value if hasattr(psa.social_account.platform, "value") else str(psa.social_account.platform)
                    post_platforms.append(plat_val)

            # Sum metrics across metrics rows for this post
            p_likes = sum(m.likes for m in post.metrics)
            p_comments = sum(m.comments for m in post.metrics)
            p_shares = sum(m.shares for m in post.metrics)
            p_clicks = sum(m.clicks for m in post.metrics)
            p_impressions = sum(m.impressions for m in post.metrics)
            p_reach = sum(m.reach for m in post.metrics)
            p_eng = p_likes + p_comments + p_shares + p_clicks
            p_eng_rate = round((p_eng / p_impressions * 100.0), 2) if p_impressions > 0 else 0.0

            total_likes += p_likes
            total_comments += p_comments
            total_shares += p_shares
            total_clicks += p_clicks
            total_impressions += p_impressions
            total_reach += p_reach
            if post.metrics:
                engagement_rates.append(p_eng_rate)

            # Platform breakdown aggregation
            for plat in (post_platforms or ["unknown"]):
                if plat not in platform_agg:
                    platform_agg[plat] = {
                        "platform": plat,
                        "post_count": 0,
                        "likes": 0,
                        "comments": 0,
                        "shares": 0,
                        "clicks": 0,
                        "impressions": 0,
                        "reach": 0,
                        "engagement_rates": [],
                    }
                platform_agg[plat]["post_count"] += 1
                platform_agg[plat]["likes"] += p_likes
                platform_agg[plat]["comments"] += p_comments
                platform_agg[plat]["shares"] += p_shares
                platform_agg[plat]["clicks"] += p_clicks
                platform_agg[plat]["impressions"] += p_impressions
                platform_agg[plat]["reach"] += p_reach
                if p_eng_rate > 0:
                    platform_agg[plat]["engagement_rates"].append(p_eng_rate)

            # Daily trend aggregation (based on published_at or created_at)
            ref_date = post.published_at or post.scheduled_at or post.created_at
            date_key = ref_date.strftime("%Y-%m-%d") if ref_date else datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if date_key not in daily_agg:
                daily_agg[date_key] = {
                    "date": date_key,
                    "posts_count": 0,
                    "likes": 0,
                    "comments": 0,
                    "shares": 0,
                    "clicks": 0,
                    "impressions": 0,
                    "reach": 0,
                }
            daily_agg[date_key]["posts_count"] += 1
            daily_agg[date_key]["likes"] += p_likes
            daily_agg[date_key]["comments"] += p_comments
            daily_agg[date_key]["shares"] += p_shares
            daily_agg[date_key]["clicks"] += p_clicks
            daily_agg[date_key]["impressions"] += p_impressions
            daily_agg[date_key]["reach"] += p_reach

            # Prepare top post candidate
            raw_content = post.content or ""
            top_post_items.append(
                TopPostItem(
                    post_id=post.id,
                    content=raw_content[:140] + ("..." if len(raw_content) > 140 else ""),
                    post_type=post.post_type or "text",
                    status=status_str,
                    platforms=post_platforms,
                    published_at=post.published_at,
                    likes=p_likes,
                    comments=p_comments,
                    shares=p_shares,
                    clicks=p_clicks,
                    impressions=p_impressions,
                    reach=p_reach,
                    engagement_rate=round(p_eng_rate, 2),
                    campaign_id=post.campaign_id,
                    campaign_name=post.campaign.name if post.campaign else None,
                )
            )

        # Sort top posts by total engagements descending
        top_post_items.sort(
            key=lambda item: (item.likes + item.comments + item.shares + item.clicks, item.impressions),
            reverse=True,
        )

        # Sort trend data points by date
        sorted_trend = [
            TrendDataPoint(**daily_agg[k]) for k in sorted(daily_agg.keys())
        ]

        # Format platform summaries
        by_platform_list = []
        for plat, data in platform_agg.items():
            rates = data.pop("engagement_rates", [])
            avg_rate = round(sum(rates) / len(rates), 2) if rates else 0.0
            by_platform_list.append(
                PlatformMetricsSummary(
                    **data,
                    avg_engagement_rate=avg_rate,
                )
            )

        overall_avg_eng = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0.0

        overview = ContentAnalyticsOverview(
            total_posts=total_posts,
            published_posts=published_posts,
            scheduled_posts=scheduled_posts,
            draft_posts=draft_posts,
            failed_posts=failed_posts,
            total_likes=total_likes,
            total_comments=total_comments,
            total_shares=total_shares,
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            total_reach=total_reach,
            avg_engagement_rate=overall_avg_eng,
        )

        return ContentAnalyticsResponse(
            overview=overview,
            by_platform=by_platform_list,
            top_posts=top_post_items[:20],
            trend=sorted_trend,
            time_range={
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
        )

    @staticmethod
    def get_audience_analytics(
        db: Session,
        user_id: str,
    ) -> AudienceAnalyticsResponse:
        """
        Return real audience summary from authenticated connected social accounts.
        Explicitly notes when platform API restrictions limit demographic breakdowns.
        """
        accounts = db.query(SocialAccount).filter(SocialAccount.user_id == user_id).all()

        total_connected = len(accounts)
        active_count = 0
        total_followers = 0
        has_any_followers_tracked = False

        account_summaries = []
        by_platform_count: Dict[str, int] = {}

        for acc in accounts:
            plat = acc.platform.value if hasattr(acc.platform, "value") else str(acc.platform)
            stat = acc.status.value if hasattr(acc.status, "value") else str(acc.status)
            if stat == "connected":
                active_count += 1
            by_platform_count[plat] = by_platform_count.get(plat, 0) + 1

            # Extract followers count if available from platform profile data
            followers = None
            following = None
            if hasattr(acc, "token_metadata") and isinstance(acc.token_metadata, dict):
                followers = acc.token_metadata.get("followers_count") or acc.token_metadata.get("follower_count")
                following = acc.token_metadata.get("friends_count") or acc.token_metadata.get("following_count")
                if followers is not None:
                    try:
                        followers = int(followers)
                        total_followers += followers
                        has_any_followers_tracked = True
                    except (ValueError, TypeError):
                        followers = None

            account_summaries.append(
                AccountAudienceSummary(
                    account_id=acc.id,
                    platform=plat,
                    account_name=acc.account_name,
                    account_username=acc.account_username,
                    status=stat,
                    followers_count=followers,
                    following_count=following,
                    data_source="social_accounts",
                    last_synced_at=acc.updated_at,
                )
            )

        return AudienceAnalyticsResponse(
            total_connected_accounts=total_connected,
            active_accounts=active_count,
            total_followers_tracked=total_followers if has_any_followers_tracked else None,
            by_account=account_summaries,
            by_platform=by_platform_count,
        )

    @staticmethod
    def get_campaign_metrics_summary(
        campaign: Campaign,
    ) -> CampaignMetricsSummary:
        """
        Compute performance and ROI metrics for a single campaign.
        """
        posts = campaign.posts or []
        total_posts = len(posts)
        published_posts = 0
        scheduled_posts = 0
        draft_posts = 0
        failed_posts = 0

        total_likes = 0
        total_comments = 0
        total_shares = 0
        total_clicks = 0
        total_impressions = 0
        total_reach = 0
        engagement_rates = []

        for p in posts:
            stat_val = p.status.value if hasattr(p.status, "value") else str(p.status).lower()
            if stat_val == PostStatus.published.value:
                published_posts += 1
            elif stat_val == PostStatus.scheduled.value:
                scheduled_posts += 1
            elif stat_val == PostStatus.draft.value:
                draft_posts += 1
            elif stat_val == PostStatus.failed.value:
                failed_posts += 1

            p_likes = sum(m.likes for m in p.metrics)
            p_comments = sum(m.comments for m in p.metrics)
            p_shares = sum(m.shares for m in p.metrics)
            p_clicks = sum(m.clicks for m in p.metrics)
            p_impressions = sum(m.impressions for m in p.metrics)
            p_reach = sum(m.reach for m in p.metrics)
            p_eng = p_likes + p_comments + p_shares + p_clicks
            p_eng_rate = round((p_eng / p_impressions * 100.0), 2) if p_impressions > 0 else 0.0

            total_likes += p_likes
            total_comments += p_comments
            total_shares += p_shares
            total_clicks += p_clicks
            total_impressions += p_impressions
            total_reach += p_reach
            if p.metrics:
                engagement_rates.append(p_eng_rate)

        total_engagements = total_likes + total_comments + total_shares + total_clicks
        progress_percentage = (
            round((published_posts / total_posts) * 100.0, 1)
            if total_posts > 0
            else 0.0
        )
        avg_eng_rate = (
            round(sum(engagement_rates) / len(engagement_rates), 2)
            if engagement_rates
            else 0.0
        )

        budget = float(campaign.budget or 0.0)
        revenue = float(campaign.revenue) if campaign.revenue is not None else None
        conversions = int(campaign.conversions or 0)

        # ROI Calculation (Honest: only calculated if revenue is tracked)
        roi_available = revenue is not None
        roi_percentage = None
        if roi_available:
            if budget > 0:
                roi_percentage = round(((revenue - budget) / budget) * 100.0, 2)
            else:
                # If budget is 0 and revenue > 0, ROI is 100% (or positive return without spend)
                roi_percentage = 100.0 if revenue > 0 else 0.0

        # Performance Ratios
        cpc = round(budget / total_clicks, 2) if (total_clicks > 0 and budget > 0) else None
        cpa = round(budget / conversions, 2) if (conversions > 0 and budget > 0) else None
        ctr = round((total_clicks / total_impressions) * 100.0, 2) if total_impressions > 0 else None
        conversion_rate = round((conversions / total_clicks) * 100.0, 2) if total_clicks > 0 else None

        return CampaignMetricsSummary(
            campaign_id=campaign.id,
            name=campaign.name,
            status=campaign.status,
            platform=campaign.platform,
            objective=campaign.objective,
            start_date=campaign.start_date,
            end_date=campaign.end_date,
            budget=budget,
            revenue=revenue,
            conversions=conversions,
            total_posts=total_posts,
            published_posts=published_posts,
            scheduled_posts=scheduled_posts,
            draft_posts=draft_posts,
            failed_posts=failed_posts,
            progress_percentage=progress_percentage,
            total_likes=total_likes,
            total_comments=total_comments,
            total_shares=total_shares,
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            total_reach=total_reach,
            total_engagements=total_engagements,
            avg_engagement_rate=avg_eng_rate,
            roi_available=roi_available,
            roi_percentage=roi_percentage,
            cpc=cpc,
            cpa=cpa,
            ctr=ctr,
            conversion_rate=conversion_rate,
        )

    @classmethod
    def get_campaign_analytics(
        cls,
        db: Session,
        user_id: str,
        campaign_id: Optional[str] = None,
    ) -> CampaignAnalyticsResponse:
        """
        Retrieve campaign analytics for all campaigns or a specific campaign.
        """
        query = db.query(Campaign).options(
            joinedload(Campaign.posts).joinedload(Post.metrics)
        ).filter(Campaign.user_id == user_id)

        if campaign_id:
            query = query.filter(Campaign.id == campaign_id)

        campaigns = query.order_by(Campaign.created_at.desc()).all()

        summaries = [cls.get_campaign_metrics_summary(c) for c in campaigns]

        total_budget = sum(s.budget for s in summaries)
        total_revenue = sum(s.revenue for s in summaries if s.revenue is not None)
        total_conversions = sum(s.conversions for s in summaries)
        total_campaign_posts = sum(s.total_posts for s in summaries)
        total_campaign_engagements = sum(s.total_engagements for s in summaries)

        overview = {
            "total_campaigns": len(summaries),
            "active_campaigns": len([s for s in summaries if s.status == "active"]),
            "total_budget": round(total_budget, 2),
            "total_revenue": round(total_revenue, 2) if any(s.revenue is not None for s in summaries) else None,
            "total_conversions": total_conversions,
            "total_posts": total_campaign_posts,
            "total_engagements": total_campaign_engagements,
        }

        return CampaignAnalyticsResponse(
            overview=overview,
            campaigns=summaries,
        )

    @classmethod
    def compare_campaigns(
        cls,
        db: Session,
        user_id: str,
        campaign_ids: List[str],
    ) -> CampaignComparisonResponse:
        """
        Compare multiple campaigns side-by-side.
        """
        campaigns = db.query(Campaign).options(
            joinedload(Campaign.posts).joinedload(Post.metrics)
        ).filter(
            Campaign.user_id == user_id,
            Campaign.id.in_(campaign_ids),
        ).all()

        summaries = [cls.get_campaign_metrics_summary(c) for c in campaigns]

        # Winner by total engagements
        winner_eng = None
        if summaries:
            best_eng = max(summaries, key=lambda s: s.total_engagements)
            winner_eng = {
                "campaign_id": best_eng.campaign_id,
                "name": best_eng.name,
                "total_engagements": best_eng.total_engagements,
            }

        # Winner by ROI (among those where ROI is available)
        winner_roi = None
        roi_candidates = [s for s in summaries if s.roi_available and s.roi_percentage is not None]
        if roi_candidates:
            best_roi = max(roi_candidates, key=lambda s: s.roi_percentage)
            winner_roi = {
                "campaign_id": best_roi.campaign_id,
                "name": best_roi.name,
                "roi_percentage": best_roi.roi_percentage,
            }

        # Comparative matrix structure
        matrix: Dict[str, Dict[str, Any]] = {
            "budget": {s.name: s.budget for s in summaries},
            "revenue": {s.name: s.revenue for s in summaries},
            "conversions": {s.name: s.conversions for s in summaries},
            "total_posts": {s.name: s.total_posts for s in summaries},
            "published_posts": {s.name: s.published_posts for s in summaries},
            "total_engagements": {s.name: s.total_engagements for s in summaries},
            "total_impressions": {s.name: s.total_impressions for s in summaries},
            "avg_engagement_rate": {s.name: s.avg_engagement_rate for s in summaries},
            "roi_percentage": {s.name: s.roi_percentage for s in summaries},
            "cpc": {s.name: s.cpc for s in summaries},
            "cpa": {s.name: s.cpa for s in summaries},
        }

        return CampaignComparisonResponse(
            compared_campaigns=summaries,
            winner_by_engagement=winner_eng,
            winner_by_roi=winner_roi,
            comparison_matrix=matrix,
        )

    @classmethod
    def export_analytics_csv(
        cls,
        db: Session,
        user_id: str,
        export_type: str = "all",
    ) -> str:
        """
        Generate CSV export of analytics and campaign data.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        if export_type in ("all", "posts"):
            writer.writerow(["=== POSTS PERFORMANCE ANALYTICS ==="])
            writer.writerow([
                "Post ID", "Content", "Type", "Status", "Published At",
                "Platforms", "Likes", "Comments", "Shares", "Clicks",
                "Impressions", "Reach", "Engagement Rate %", "Campaign"
            ])
            posts_data = cls.get_content_analytics(db, user_id)
            for p in posts_data.top_posts:
                writer.writerow([
                    p.post_id,
                    (p.content or "").replace("\n", " "),
                    p.post_type,
                    p.status,
                    p.published_at.isoformat() if p.published_at else "N/A",
                    ", ".join(p.platforms),
                    p.likes,
                    p.comments,
                    p.shares,
                    p.clicks,
                    p.impressions,
                    p.reach,
                    p.engagement_rate,
                    p.campaign_name or "None",
                ])
            writer.writerow([])

        if export_type in ("all", "campaigns"):
            writer.writerow(["=== CAMPAIGNS PERFORMANCE & ROI ==="])
            writer.writerow([
                "Campaign ID", "Campaign Name", "Status", "Platform",
                "Objective", "Budget ($)", "Revenue ($)", "Conversions",
                "Total Posts", "Published Posts", "Total Engagements",
                "Impressions", "Reach", "ROI %", "CPC ($)", "CPA ($)"
            ])
            camp_data = cls.get_campaign_analytics(db, user_id)
            for c in camp_data.campaigns:
                writer.writerow([
                    c.campaign_id,
                    c.name,
                    c.status,
                    c.platform or "All",
                    c.objective or "N/A",
                    c.budget,
                    c.revenue if c.revenue is not None else "Not Tracked",
                    c.conversions,
                    c.total_posts,
                    c.published_posts,
                    c.total_engagements,
                    c.total_impressions,
                    c.total_reach,
                    f"{c.roi_percentage}%" if c.roi_percentage is not None else "N/A",
                    c.cpc if c.cpc is not None else "N/A",
                    c.cpa if c.cpa is not None else "N/A",
                ])

        return output.getvalue()
