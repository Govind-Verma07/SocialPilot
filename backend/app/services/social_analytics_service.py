"""
app/services/social_analytics_service.py
-----------------------------------------
Official Real Social Media Analytics Integration Service.
Handles:
- Fetching real performance and engagement metrics from connected social platform APIs
  (LinkedIn, Facebook, Instagram, YouTube, X / Twitter, Pinterest).
- Normalizing platform-specific metric payloads into standard PostMetric schemas.
- Persisting / updating PostMetric snapshots without creating duplicate rows.
- Account-level diagnostic status and permission inspection.
- Scheduled & on-demand synchronization routines.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy.orm import Session, joinedload

from app.core.encryption import decrypt_token
from app.models.analytics import PostMetric
from app.models.enums import PostStatus, SocialPlatform, AccountStatus
from app.models.post import Post
from app.models.post_publish_result import PostPublishResult
from app.models.social_account import SocialAccount

logger = logging.getLogger("socialpilot.analytics")


class PlatformMetricResult:
    """Normalized metrics container extracted from a social media platform API."""

    def __init__(
        self,
        platform: str,
        impressions: int = 0,
        reach: int = 0,
        engagement: int = 0,
        clicks: int = 0,
        likes: int = 0,
        comments: int = 0,
        shares: int = 0,
        video_views: int = 0,
        raw_response: Optional[Dict[str, Any]] = None,
        is_available: bool = True,
        status_message: Optional[str] = None,
    ):
        self.platform = platform
        self.impressions = impressions
        self.reach = reach
        self.engagement = engagement
        self.clicks = clicks
        self.likes = likes
        self.comments = comments
        self.shares = shares
        self.video_views = video_views
        self.raw_response = raw_response or {}
        self.is_available = is_available
        self.status_message = status_message


class SocialAnalyticsService:

    # -----------------------------------------------------------------------
    # 1. Platform-Specific Real Analytics Fetchers
    # -----------------------------------------------------------------------

    @staticmethod
    async def fetch_linkedin_metrics(
        token: str,
        platform_post_id: str,
    ) -> PlatformMetricResult:
        """
        Fetch real analytics for a published LinkedIn update/post.
        Uses LinkedIn's socialActions and reactions APIs.
        `platform_post_id` is the URN, e.g. 'urn:li:ugcPost:12345' or 'urn:li:share:12345'.
        """
        likes = 0
        comments = 0
        shares = 0
        impressions = 0
        reach = 0
        clicks = 0

        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Accept": "application/json",
        }

        # 1. Fetch likes and comments summary via socialActions
        # URL encode the URN: colons become %3A
        encoded_urn = platform_post_id.replace(":", "%3A")
        url = f"https://api.linkedin.com/v2/socialActions/{encoded_urn}"

        raw_data = {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    raw_data = resp.json()
                    comments_summary = raw_data.get("commentsSummary", {})
                    likes_summary = raw_data.get("likesSummary", {})
                    comments = comments_summary.get("aggregatedTotalComments", 0)
                    likes = likes_summary.get("aggregatedTotalLikes", 0)
                elif resp.status_code == 401:
                    logger.warning("LinkedIn token expired or unauthorized for post %s", platform_post_id)
                    return PlatformMetricResult(
                        platform="linkedin",
                        is_available=False,
                        status_message="LinkedIn authentication expired (401). Please reconnect.",
                    )
                elif resp.status_code == 403:
                    logger.info("LinkedIn permissions restricted for post %s", platform_post_id)
                    return PlatformMetricResult(
                        platform="linkedin",
                        is_available=False,
                        status_message="LinkedIn analytics permission missing (403).",
                    )
                else:
                    logger.info("LinkedIn socialActions returned status %s for post %s", resp.status_code, platform_post_id)
            except Exception as e:
                logger.warning("Error calling LinkedIn socialActions API: %s", e)

        # Total engagements = likes + comments + shares + clicks
        engagement = likes + comments + shares + clicks

        return PlatformMetricResult(
            platform="linkedin",
            impressions=impressions,
            reach=reach,
            engagement=engagement,
            clicks=clicks,
            likes=likes,
            comments=comments,
            shares=shares,
            video_views=0,
            raw_response=raw_data,
            is_available=True,
            status_message="Live metrics synced from LinkedIn",
        )

    @staticmethod
    async def fetch_facebook_metrics(
        token: str,
        platform_post_id: str,
    ) -> PlatformMetricResult:
        """
        Fetch real analytics for a Facebook Page post.
        Uses Graph API: /{post_id}?fields=shares,reactions.summary(total_count),comments.summary(total_count),insights.metric(...)
        """
        url = f"https://graph.facebook.com/v19.0/{platform_post_id}"
        params = {
            "fields": "shares,reactions.summary(total_count),comments.summary(total_count),insights.metric(post_impressions,post_engaged_users,post_clicks)",
            "access_token": token,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    reactions_count = data.get("reactions", {}).get("summary", {}).get("total_count", 0)
                    comments_count = data.get("comments", {}).get("summary", {}).get("total_count", 0)
                    shares_count = data.get("shares", {}).get("count", 0)

                    impressions = 0
                    clicks = 0
                    reach = 0

                    insights = data.get("insights", {}).get("data", [])
                    for ins in insights:
                        name = ins.get("name")
                        values = ins.get("values", [])
                        val = values[0].get("value", 0) if values else 0
                        if name == "post_impressions":
                            impressions = int(val) if isinstance(val, (int, float)) else 0
                        elif name == "post_engaged_users":
                            reach = int(val) if isinstance(val, (int, float)) else 0
                        elif name == "post_clicks":
                            clicks = int(val) if isinstance(val, (int, float)) else 0

                    engagement = reactions_count + comments_count + shares_count + clicks

                    return PlatformMetricResult(
                        platform="facebook",
                        impressions=impressions,
                        reach=reach,
                        engagement=engagement,
                        clicks=clicks,
                        likes=reactions_count,
                        comments=comments_count,
                        shares=shares_count,
                        video_views=0,
                        raw_response=data,
                        is_available=True,
                        status_message="Live metrics synced from Facebook Graph API",
                    )
                elif resp.status_code in (401, 403):
                    return PlatformMetricResult(
                        platform="facebook",
                        is_available=False,
                        status_message=f"Facebook API authorization error ({resp.status_code}).",
                    )
                else:
                    return PlatformMetricResult(
                        platform="facebook",
                        is_available=False,
                        status_message=f"Facebook API returned status {resp.status_code}.",
                    )
            except Exception as e:
                logger.warning("Error fetching Facebook metrics: %s", e)
                return PlatformMetricResult(
                    platform="facebook",
                    is_available=False,
                    status_message=f"Network error communicating with Facebook: {e}",
                )

    @staticmethod
    async def fetch_instagram_metrics(
        token: str,
        platform_post_id: str,
    ) -> PlatformMetricResult:
        """
        Fetch real analytics for an Instagram Media object.
        Uses Graph API: /{media_id}?fields=like_count,comments_count,media_type,insights.metric(impressions,reach,saved,total_interactions)
        """
        url = f"https://graph.facebook.com/v19.0/{platform_post_id}"
        params = {
            "fields": "like_count,comments_count,media_type,insights.metric(impressions,reach,saved,total_interactions)",
            "access_token": token,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    likes = data.get("like_count", 0)
                    comments = data.get("comments_count", 0)

                    impressions = 0
                    reach = 0
                    saved = 0
                    total_interactions = 0

                    insights = data.get("insights", {}).get("data", [])
                    for ins in insights:
                        name = ins.get("name")
                        values = ins.get("values", [])
                        val = values[0].get("value", 0) if values else 0
                        if name == "impressions":
                            impressions = int(val) if isinstance(val, (int, float)) else 0
                        elif name == "reach":
                            reach = int(val) if isinstance(val, (int, float)) else 0
                        elif name == "saved":
                            saved = int(val) if isinstance(val, (int, float)) else 0
                        elif name == "total_interactions":
                            total_interactions = int(val) if isinstance(val, (int, float)) else 0

                    engagement = total_interactions if total_interactions > 0 else (likes + comments + saved)

                    return PlatformMetricResult(
                        platform="instagram",
                        impressions=impressions,
                        reach=reach,
                        engagement=engagement,
                        clicks=0,
                        likes=likes,
                        comments=comments,
                        shares=saved,
                        video_views=0,
                        raw_response=data,
                        is_available=True,
                        status_message="Live metrics synced from Instagram Graph API",
                    )
                elif resp.status_code in (401, 403):
                    return PlatformMetricResult(
                        platform="instagram",
                        is_available=False,
                        status_message=f"Instagram API authorization error ({resp.status_code}).",
                    )
                else:
                    return PlatformMetricResult(
                        platform="instagram",
                        is_available=False,
                        status_message=f"Instagram API returned status {resp.status_code}.",
                    )
            except Exception as e:
                logger.warning("Error fetching Instagram metrics: %s", e)
                return PlatformMetricResult(
                    platform="instagram",
                    is_available=False,
                    status_message=f"Network error communicating with Instagram: {e}",
                )

    @staticmethod
    async def fetch_youtube_metrics(
        token: str,
        platform_post_id: str,
    ) -> PlatformMetricResult:
        """
        Fetch real video statistics for YouTube.
        Uses YouTube Data API v3: videos?part=statistics&id={video_id}
        """
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "statistics",
            "id": platform_post_id,
        }
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    if items:
                        stats = items[0].get("statistics", {})
                        views = int(stats.get("viewCount", 0))
                        likes = int(stats.get("likeCount", 0))
                        comments = int(stats.get("commentCount", 0))
                        engagement = likes + comments

                        return PlatformMetricResult(
                            platform="youtube",
                            impressions=views,
                            reach=views,
                            engagement=engagement,
                            clicks=0,
                            likes=likes,
                            comments=comments,
                            shares=0,
                            video_views=views,
                            raw_response=stats,
                            is_available=True,
                            status_message="Live metrics synced from YouTube Data API",
                        )
                    else:
                        return PlatformMetricResult(
                            platform="youtube",
                            is_available=False,
                            status_message="Video not found on YouTube or not public.",
                        )
                else:
                    return PlatformMetricResult(
                        platform="youtube",
                        is_available=False,
                        status_message=f"YouTube API returned status {resp.status_code}.",
                    )
            except Exception as e:
                logger.warning("Error fetching YouTube metrics: %s", e)
                return PlatformMetricResult(
                    platform="youtube",
                    is_available=False,
                    status_message=f"Network error communicating with YouTube: {e}",
                )

    @staticmethod
    async def fetch_x_metrics(
        token: str,
        platform_post_id: str,
    ) -> PlatformMetricResult:
        """
        Fetch real public metrics for an X / Twitter Tweet.
        Uses X API v2: /2/tweets/{tweet_id}?tweet.fields=public_metrics
        """
        url = f"https://api.twitter.com/2/tweets/{platform_post_id}"
        params = {"tweet.fields": "public_metrics,non_public_metrics"}
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    pub_metrics = data.get("public_metrics", {})
                    likes = pub_metrics.get("like_count", 0)
                    retweets = pub_metrics.get("retweet_count", 0)
                    replies = pub_metrics.get("reply_count", 0)
                    quotes = pub_metrics.get("quote_count", 0)
                    impressions = pub_metrics.get("impression_count", 0)

                    shares = retweets + quotes
                    comments = replies
                    engagement = likes + shares + comments

                    return PlatformMetricResult(
                        platform="x",
                        impressions=impressions,
                        reach=impressions,
                        engagement=engagement,
                        clicks=0,
                        likes=likes,
                        comments=comments,
                        shares=shares,
                        video_views=0,
                        raw_response=data,
                        is_available=True,
                        status_message="Live metrics synced from X API v2",
                    )
                elif resp.status_code in (401, 403):
                    return PlatformMetricResult(
                        platform="x",
                        is_available=False,
                        status_message="X API authorization restricted or insufficient permission tier.",
                    )
                else:
                    return PlatformMetricResult(
                        platform="x",
                        is_available=False,
                        status_message=f"X API returned status {resp.status_code}.",
                    )
            except Exception as e:
                logger.warning("Error fetching X metrics: %s", e)
                return PlatformMetricResult(
                    platform="x",
                    is_available=False,
                    status_message=f"Network error communicating with X: {e}",
                )

    @staticmethod
    async def fetch_pinterest_metrics(
        token: str,
        platform_post_id: str,
    ) -> PlatformMetricResult:
        """
        Fetch real analytics for a Pinterest Pin.
        Uses Pinterest API v5: /v5/pins/{pin_id}/analytics
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        url = f"https://api.pinterest.com/v5/pins/{platform_post_id}/analytics"
        params = {
            "start_date": thirty_days_ago,
            "end_date": today,
            "metric_types": "IMPRESSION,PIN_CLICK,SAVE",
        }
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    summary = data.get("summary_metrics", {})
                    impressions = int(summary.get("IMPRESSION", 0))
                    clicks = int(summary.get("PIN_CLICK", 0))
                    saves = int(summary.get("SAVE", 0))
                    engagement = clicks + saves

                    return PlatformMetricResult(
                        platform="pinterest",
                        impressions=impressions,
                        reach=impressions,
                        engagement=engagement,
                        clicks=clicks,
                        likes=0,
                        comments=0,
                        shares=saves,
                        video_views=0,
                        raw_response=data,
                        is_available=True,
                        status_message="Live metrics synced from Pinterest API v5",
                    )
                elif resp.status_code in (401, 403):
                    return PlatformMetricResult(
                        platform="pinterest",
                        is_available=False,
                        status_message="Pinterest API authorization error (401/403).",
                    )
                else:
                    return PlatformMetricResult(
                        platform="pinterest",
                        is_available=False,
                        status_message=f"Pinterest API returned status {resp.status_code}.",
                    )
            except Exception as e:
                logger.warning("Error fetching Pinterest metrics: %s", e)
                return PlatformMetricResult(
                    platform="pinterest",
                    is_available=False,
                    status_message=f"Network error communicating with Pinterest: {e}",
                )

    # -----------------------------------------------------------------------
    # 2. Dispatcher and PostMetric Upsert Logic
    # -----------------------------------------------------------------------

    @classmethod
    async def fetch_metrics_for_publish_result(
        cls,
        db: Session,
        publish_result: PostPublishResult,
    ) -> Optional[PostMetric]:
        """
        Fetch real metrics from the external platform for a given PostPublishResult,
        and upsert a PostMetric record in PostgreSQL.
        """
        if not publish_result.platform_post_id:
            logger.debug("No platform_post_id for publish_result #%s. Skipping.", publish_result.id)
            return None

        account = db.query(SocialAccount).filter(SocialAccount.id == publish_result.social_account_id).first()
        if not account or not account.access_token_encrypted:
            logger.debug("No active social account or token for publish_result #%s", publish_result.id)
            return None

        raw_token = decrypt_token(account.access_token_encrypted)
        if not raw_token:
            logger.warning("Could not decrypt token for account #%s", account.id)
            return None

        platform_str = publish_result.platform.lower()
        res: Optional[PlatformMetricResult] = None

        if platform_str == SocialPlatform.linkedin.value or platform_str == "linkedin":
            res = await cls.fetch_linkedin_metrics(raw_token, publish_result.platform_post_id)
        elif platform_str == SocialPlatform.facebook.value or platform_str == "facebook":
            res = await cls.fetch_facebook_metrics(raw_token, publish_result.platform_post_id)
        elif platform_str == SocialPlatform.instagram.value or platform_str == "instagram":
            res = await cls.fetch_instagram_metrics(raw_token, publish_result.platform_post_id)
        elif platform_str == SocialPlatform.youtube.value or platform_str == "youtube":
            res = await cls.fetch_youtube_metrics(raw_token, publish_result.platform_post_id)
        elif platform_str == SocialPlatform.x.value or platform_str == "x" or platform_str == "twitter":
            res = await cls.fetch_x_metrics(raw_token, publish_result.platform_post_id)
        elif platform_str == SocialPlatform.pinterest.value or platform_str == "pinterest":
            res = await cls.fetch_pinterest_metrics(raw_token, publish_result.platform_post_id)
        else:
            logger.info("Unsupported platform '%s' for metrics sync", platform_str)
            return None

        if not res or not res.is_available:
            logger.info(
                "Metric fetch skipped/unavailable for post #%s on %s: %s",
                publish_result.post_id,
                platform_str,
                res.status_message if res else "No response",
            )
            return None

        # Upsert into post_metrics table
        now = datetime.now(timezone.utc)
        existing_metric = (
            db.query(PostMetric)
            .filter(
                PostMetric.post_id == publish_result.post_id,
                PostMetric.social_account_id == publish_result.social_account_id,
            )
            .first()
        )

        if not existing_metric:
            existing_metric = (
                db.query(PostMetric)
                .filter(
                    PostMetric.post_id == publish_result.post_id,
                    PostMetric.platform == platform_str,
                )
                .first()
            )

        if existing_metric:
            existing_metric.impressions = res.impressions
            existing_metric.reach = res.reach
            existing_metric.engagement = res.engagement
            existing_metric.clicks = res.clicks
            existing_metric.likes = res.likes
            existing_metric.comments = res.comments
            existing_metric.shares = res.shares
            existing_metric.video_views = res.video_views
            existing_metric.captured_at = now
            existing_metric.is_real = True
            db.commit()
            db.refresh(existing_metric)
            logger.debug(
                "Updated PostMetric for post #%s on %s (eng=%d)",
                publish_result.post_id,
                platform_str,
                res.engagement,
            )
            return existing_metric

        new_metric = PostMetric(
            post_id=publish_result.post_id,
            social_account_id=publish_result.social_account_id,
            platform=platform_str,
            impressions=res.impressions,
            reach=res.reach,
            engagement=res.engagement,
            clicks=res.clicks,
            likes=res.likes,
            comments=res.comments,
            shares=res.shares,
            video_views=res.video_views,
            is_real=True,
            captured_at=now,
        )
        db.add(new_metric)
        db.commit()
        db.refresh(new_metric)
        logger.debug(
            "Created new PostMetric for post #%s on %s (eng=%d)",
            publish_result.post_id,
            platform_str,
            res.engagement,
        )
        return new_metric

    # -----------------------------------------------------------------------
    # 3. Synchronization Pipelines
    # -----------------------------------------------------------------------

    @classmethod
    async def sync_user_analytics(
        cls,
        db: Session,
        user_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Synchronize real social metrics for all published posts of a given user
        created or published within the last `days` days.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        posts = (
            db.query(Post)
            .options(
                joinedload(Post.publish_results),
                joinedload(Post.social_accounts),
            )
            .filter(
                Post.user_id == user_id,
                Post.status == PostStatus.published.value,
                Post.created_at >= cutoff,
            )
            .all()
        )

        synced_posts = 0
        metrics_updated = 0
        errors = []

        for p in posts:
            for pr in p.publish_results:
                if pr.status == "published" and pr.platform_post_id:
                    try:
                        metric = await cls.fetch_metrics_for_publish_result(db, pr)
                        if metric:
                            metrics_updated += 1
                    except Exception as exc:
                        err_msg = f"Failed to sync post #{p.id} on {pr.platform}: {str(exc)}"
                        logger.warning(err_msg)
                        errors.append(err_msg)
            synced_posts += 1

        # Update last_synced_at on user's active social accounts
        now = datetime.now(timezone.utc)
        user_accounts = (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == user_id, SocialAccount.status == AccountStatus.connected.value)
            .all()
        )
        for acc in user_accounts:
            acc.last_synced_at = now
        db.commit()

        return {
            "user_id": user_id,
            "synced_posts_count": synced_posts,
            "metrics_updated_count": metrics_updated,
            "accounts_synced": len(user_accounts),
            "errors": errors,
            "synced_at": now.isoformat(),
        }

    @classmethod
    def get_platform_diagnostics(
        cls,
        db: Session,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate diagnostic status for all connected social accounts of the user.
        Clarifies whether live analytics permissions and tokens are valid.
        """
        accounts = (
            db.query(SocialAccount)
            .filter(SocialAccount.user_id == user_id)
            .order_by(SocialAccount.platform.asc())
            .all()
        )

        platform_specs = {
            "linkedin": {
                "name": "LinkedIn",
                "metrics": ["Likes / Reactions", "Comments", "Post Engagements"],
                "required_scope": "openid profile w_member_social",
            },
            "facebook": {
                "name": "Facebook",
                "metrics": ["Impressions", "Reactions", "Comments", "Shares", "Post Clicks"],
                "required_scope": "pages_read_engagement,pages_manage_posts",
            },
            "instagram": {
                "name": "Instagram",
                "metrics": ["Impressions", "Reach", "Likes", "Comments", "Saves"],
                "required_scope": "instagram_business_basic,instagram_manage_insights",
            },
            "youtube": {
                "name": "YouTube",
                "metrics": ["Views", "Likes", "Comments", "Video Views"],
                "required_scope": "youtube.readonly",
            },
            "x": {
                "name": "X (Twitter)",
                "metrics": ["Likes", "Retweets", "Replies", "Quotes", "Public Impressions"],
                "required_scope": "tweet.read,users.read",
            },
            "pinterest": {
                "name": "Pinterest",
                "metrics": ["Impressions", "Pin Clicks", "Saves"],
                "required_scope": "boards:read,pins:read",
            },
        }

        diagnostics = []
        for acc in accounts:
            plat_str = acc.platform.value if hasattr(acc.platform, "value") else str(acc.platform).lower()
            spec = platform_specs.get(plat_str, {
                "name": plat_str.title(),
                "metrics": ["Impressions", "Engagement"],
                "required_scope": "Standard",
            })

            has_token = bool(acc.access_token_encrypted)
            is_connected = acc.status == AccountStatus.connected.value

            # Determine permission status
            has_permission = is_connected and has_token
            status_msg = (
                "Connected & ready for live metrics sync"
                if has_permission
                else "Account disconnected or token expired. Please reconnect."
            )

            diagnostics.append({
                "account_id": acc.id,
                "platform": plat_str,
                "display_name": spec["name"],
                "account_name": acc.account_name,
                "account_username": acc.account_username,
                "is_connected": is_connected,
                "has_analytics_permission": has_permission,
                "last_synced_at": acc.last_synced_at.isoformat() if acc.last_synced_at else None,
                "supported_metrics": spec["metrics"],
                "required_scope": spec["required_scope"],
                "status_message": status_msg,
            })

        return diagnostics
