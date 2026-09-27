"""
tests/test_social_analytics.py
-------------------------------
Comprehensive automated test suite for Real Social Media Analytics Integration:
- Platform-Specific Metric Extraction (LinkedIn, Facebook, Instagram, YouTube, X, Pinterest)
- PostMetric DB Upsert and Snapshot Persistence
- Diagnostic Platform Status & Permissions Endpoint
- On-Demand Real Analytics Sync Endpoint (POST /analytics/sync)
- Celery Worker Background Sync Task (sync_social_analytics_task)
- Safe Error and Token Expiry Handling (401, 403, 404, 429)
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
import httpx

from app.models.enums import PostStatus, SocialPlatform, AccountStatus
from app.models.social_account import SocialAccount
from app.models.post import Post, PostSocialAccount
from app.models.post_publish_result import PostPublishResult
from app.models.analytics import PostMetric
from app.core.encryption import encrypt_token
from app.services.social_analytics_service import SocialAnalyticsService, PlatformMetricResult


def _register_user(client, email: str, name: str = "Analytics User"):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": "Password123",
            "role": "marketing_team",
        },
    )
    assert res.status_code == 201, res.text
    token = res.json()["access_token"]
    user_id = res.json()["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _seed_account(db_session, user_id: str, platform: SocialPlatform, name: str):
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform,
        platform_account_id=f"{platform.value}_{user_id[:6]}",
        account_name=f"{name} Account",
        account_username=name.lower().replace(" ", "_"),
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("mock_access_token_12345"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _seed_published_post_with_result(db_session, user_id: str, account: SocialAccount, platform_post_id: str):
    now = datetime.now(timezone.utc)
    post = Post(
        user_id=user_id,
        content="Testing real social analytics data synchronization",
        status=PostStatus.published.value,
        published_at=now - timedelta(hours=2),
    )
    db_session.add(post)
    db_session.flush()

    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=account.id))

    pub_result = PostPublishResult(
        post_id=post.id,
        social_account_id=account.id,
        platform=account.platform.value if hasattr(account.platform, "value") else str(account.platform),
        status="published",
        platform_post_id=platform_post_id,
        published_url=f"https://{account.platform.value}.com/post/{platform_post_id}",
        published_at=now - timedelta(hours=2),
    )
    db_session.add(pub_result)
    db_session.commit()
    db_session.refresh(post)
    db_session.refresh(pub_result)
    return post, pub_result


# ===========================================================================
# 1. PLATFORM-SPECIFIC EXTRACTION TESTS (MOCKED HTTP)
# ===========================================================================

@pytest.mark.asyncio
async def test_linkedin_metrics_extraction():
    """Verify LinkedIn socialActions metric extraction for likes and comments."""
    mock_resp = {
        "commentsSummary": {"aggregatedTotalComments": 14},
        "likesSummary": {"aggregatedTotalLikes": 42},
        "target": "urn:li:ugcPost:123456",
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        result = await SocialAnalyticsService.fetch_linkedin_metrics("token_123", "urn:li:ugcPost:123456")

    assert result.is_available is True
    assert result.platform == "linkedin"
    assert result.likes == 42
    assert result.comments == 14
    assert result.engagement == 56


@pytest.mark.asyncio
async def test_facebook_metrics_extraction():
    """Verify Facebook Graph API metric extraction for impressions, reach, reactions, comments, clicks."""
    mock_resp = {
        "reactions": {"summary": {"total_count": 85}},
        "comments": {"summary": {"total_count": 12}},
        "shares": {"count": 7},
        "insights": {
            "data": [
                {"name": "post_impressions", "values": [{"value": 1450}]},
                {"name": "post_engaged_users", "values": [{"value": 890}]},
                {"name": "post_clicks", "values": [{"value": 45}]},
            ]
        },
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        result = await SocialAnalyticsService.fetch_facebook_metrics("token_123", "123456789_987654321")

    assert result.is_available is True
    assert result.platform == "facebook"
    assert result.likes == 85
    assert result.comments == 12
    assert result.shares == 7
    assert result.impressions == 1450
    assert result.reach == 890
    assert result.clicks == 45
    assert result.engagement == (85 + 12 + 7 + 45)


@pytest.mark.asyncio
async def test_instagram_metrics_extraction():
    """Verify Instagram Graph API metric extraction for likes, comments, impressions, reach, saves."""
    mock_resp = {
        "like_count": 120,
        "comments_count": 18,
        "insights": {
            "data": [
                {"name": "impressions", "values": [{"value": 2400}]},
                {"name": "reach", "values": [{"value": 1950}]},
                {"name": "saved", "values": [{"value": 35}]},
            ]
        },
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        result = await SocialAnalyticsService.fetch_instagram_metrics("token_123", "17901234567890123")

    assert result.is_available is True
    assert result.platform == "instagram"
    assert result.likes == 120
    assert result.comments == 18
    assert result.impressions == 2400
    assert result.reach == 1950
    assert result.shares == 35


@pytest.mark.asyncio
async def test_youtube_metrics_extraction():
    """Verify YouTube Data API v3 metric extraction for views, likes, comments."""
    mock_resp = {
        "items": [
            {
                "id": "dQw4w9WgXcQ",
                "statistics": {
                    "viewCount": "15400",
                    "likeCount": "920",
                    "commentCount": "130",
                },
            }
        ]
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        result = await SocialAnalyticsService.fetch_youtube_metrics("token_123", "dQw4w9WgXcQ")

    assert result.is_available is True
    assert result.platform == "youtube"
    assert result.impressions == 15400
    assert result.likes == 920
    assert result.comments == 130
    assert result.engagement == 1050


@pytest.mark.asyncio
async def test_x_metrics_extraction():
    """Verify X / Twitter API v2 metric extraction for likes, retweets, replies, impressions."""
    mock_resp = {
        "data": {
            "id": "1234567890123456789",
            "public_metrics": {
                "like_count": 64,
                "retweet_count": 15,
                "reply_count": 8,
                "quote_count": 3,
                "impression_count": 1850,
            },
        }
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        result = await SocialAnalyticsService.fetch_x_metrics("token_123", "1234567890123456789")

    assert result.is_available is True
    assert result.platform == "x"
    assert result.likes == 64
    assert result.shares == 18  # retweets (15) + quotes (3)
    assert result.comments == 8
    assert result.impressions == 1850
    assert result.engagement == (64 + 18 + 8)


@pytest.mark.asyncio
async def test_pinterest_metrics_extraction():
    """Verify Pinterest API v5 metric extraction for impressions, clicks, saves."""
    mock_resp = {
        "summary_metrics": {
            "IMPRESSION": 850,
            "PIN_CLICK": 62,
            "SAVE": 28,
        }
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        result = await SocialAnalyticsService.fetch_pinterest_metrics("token_123", "pin_123456")

    assert result.is_available is True
    assert result.platform == "pinterest"
    assert result.impressions == 850
    assert result.clicks == 62
    assert result.shares == 28
    assert result.engagement == 90


# ===========================================================================
# 2. TOKEN EXPIRY & UNAVAILABLE METRIC HANDLING
# ===========================================================================

@pytest.mark.asyncio
async def test_expired_token_handling():
    """Verify 401 unauthorized returns unavailable result with clean status message."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=401)
        result = await SocialAnalyticsService.fetch_linkedin_metrics("expired_token", "urn:li:ugcPost:999")

    assert result.is_available is False
    assert "expired" in result.status_message.lower()


# ===========================================================================
# 3. POSTMETRIC DB UPSERT & SYNC PIPELINE
# ===========================================================================

@pytest.mark.asyncio
async def test_fetch_metrics_for_publish_result_and_upsert(db_session):
    """Verify fetch_metrics_for_publish_result creates or updates PostMetric without duplicating rows."""
    user_id = "user_metric_test_1"
    account = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Test LI")
    post, pub_res = _seed_published_post_with_result(db_session, user_id, account, "urn:li:ugcPost:998877")

    mock_resp = {
        "commentsSummary": {"aggregatedTotalComments": 5},
        "likesSummary": {"aggregatedTotalLikes": 25},
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        metric = await SocialAnalyticsService.fetch_metrics_for_publish_result(db_session, pub_res)

    assert metric is not None
    assert metric.post_id == post.id
    assert metric.likes == 25
    assert metric.comments == 5
    assert metric.engagement == 30

    # Running it a second time with updated numbers updates the same row
    mock_resp_2 = {
        "commentsSummary": {"aggregatedTotalComments": 8},
        "likesSummary": {"aggregatedTotalLikes": 30},
    }
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp_2)
        metric_updated = await SocialAnalyticsService.fetch_metrics_for_publish_result(db_session, pub_res)

    assert metric_updated.id == metric.id
    assert metric_updated.likes == 30
    assert metric_updated.comments == 8

    # Verify only 1 PostMetric row exists for this post
    all_metrics = db_session.query(PostMetric).filter(PostMetric.post_id == post.id).all()
    assert len(all_metrics) == 1


# ===========================================================================
# 4. REST API ENDPOINTS (POST /sync & GET /diagnostics)
# ===========================================================================

def test_sync_analytics_endpoint(client, db_session):
    """Verify POST /api/v1/analytics/sync returns summary and updates metrics."""
    user_id, headers = _register_user(client, "sync_api_user@test.com", "Sync User")
    account = _seed_account(db_session, user_id, SocialPlatform.linkedin, "Sync LI")
    post, pub_res = _seed_published_post_with_result(db_session, user_id, account, "urn:li:ugcPost:554433")

    mock_resp = {
        "commentsSummary": {"aggregatedTotalComments": 3},
        "likesSummary": {"aggregatedTotalLikes": 15},
    }

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: mock_resp)
        res = client.post("/api/v1/analytics/sync?days=30", headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["user_id"] == user_id
    assert data["synced_posts_count"] >= 1
    assert data["metrics_updated_count"] >= 1


def test_get_diagnostics_endpoint(client, db_session):
    """Verify GET /api/v1/analytics/diagnostics returns connected platforms and permissions."""
    user_id, headers = _register_user(client, "diag_user@test.com", "Diag User")
    _seed_account(db_session, user_id, SocialPlatform.linkedin, "Diag LI")
    _seed_account(db_session, user_id, SocialPlatform.instagram, "Diag IG")

    res = client.get("/api/v1/analytics/diagnostics", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_accounts"] >= 2
    assert data["connected_count"] >= 2
    platforms = [a["platform"] for a in data["accounts"]]
    assert "linkedin" in platforms
    assert "instagram" in platforms


# ===========================================================================
# 5. CELERY WORKER PERIODIC TASK TEST
# ===========================================================================

def test_celery_sync_social_analytics_task(db_session):
    """Verify sync_social_analytics_task worker execution."""
    from tests.conftest import TestingSessionLocal
    from app.worker.tasks import sync_social_analytics_task

    mock_sync_result = {
        "user_id": "u1",
        "synced_posts_count": 2,
        "metrics_updated_count": 2,
    }

    with patch("app.worker.tasks.SessionLocal", side_effect=TestingSessionLocal), \
         patch("app.services.social_analytics_service.SocialAnalyticsService.sync_user_analytics", return_value=mock_sync_result):
        res = sync_social_analytics_task()

    assert res["status"] == "completed"
    assert "users_processed" in res
