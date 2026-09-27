"""
tests/test_milestone3_campaigns_and_analytics.py
------------------------------------------------
Comprehensive automated test suite for Milestone 3:
- Campaign Management (CRUD, validations, user isolation)
- Campaign ↔ Post Association (attach, detach, tracking stats)
- Real Post Metrics Recording & Analytics Engine
- Content Analytics (Overview, by platform, top posts, daily trends)
- Audience Analytics (Connected accounts, followers tracking)
- Campaign Analytics & Honest ROI Calculation
- Multi-Campaign Side-by-Side Comparison
- Analytics CSV & JSON Export
"""

from datetime import datetime, timedelta, timezone
import pytest
from app.models.enums import PostStatus, SocialPlatform, AccountStatus
from app.models.social_account import SocialAccount
from app.models.post import Post, PostSocialAccount
from app.models.campaign import Campaign
from app.models.analytics import PostMetric
from app.core.encryption import encrypt_token


def _register(client, email: str, name: str = "Test User"):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": "Password123",
            "role": "marketing_team",
        },
    )
    assert res.status_code == 201
    token = res.json()["access_token"]
    user_id = res.json()["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _create_social_account(db_session, user_id: str, platform: str = "x", name: str = "Handle"):
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform,
        platform_account_id=f"{platform}_{user_id[:8]}_{name}",
        account_name=f"{name} Account",
        account_username=name.lower(),
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("dummy_token"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


# ===========================================================================
# 1. CAMPAIGN CRUD & VALIDATION TESTS
# ===========================================================================

def test_campaign_create_success(client, db_session):
    """Verify creating a campaign with full fields and default values."""
    user_id, headers = _register(client, "camp_user1@example.com", "Camp Creator")
    now = datetime.now(timezone.utc)
    start_dt = now.isoformat()
    end_dt = (now + timedelta(days=14)).isoformat()

    payload = {
        "name": "Q4 Black Friday Blitz",
        "description": "Annual promotion campaign for retail products",
        "platform": "instagram",
        "start_date": start_dt,
        "end_date": end_dt,
        "budget": 5000.0,
        "revenue": 12500.0,
        "conversions": 250,
        "objective": "conversions",
        "status": "active",
    }

    res = client.post("/api/v1/campaigns", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["name"] == "Q4 Black Friday Blitz"
    assert data["budget"] == 5000.0
    assert data["revenue"] == 12500.0
    assert data["conversions"] == 250
    assert data["status"] == "active"
    assert data["platform"] == "instagram"
    assert data["user_id"] == user_id
    assert "tracking_stats" in data
    assert data["tracking_stats"]["total_posts"] == 0


def test_campaign_validation_negative_budget_and_inverted_dates(client, db_session):
    """Verify validation rejects negative budget and end_date < start_date."""
    user_id, headers = _register(client, "camp_invalid@example.com", "Invalid Creator")
    now = datetime.now(timezone.utc)

    # 1. Negative budget
    res = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Negative Budget Campaign",
            "budget": -100.0,
        },
        headers=headers,
    )
    assert res.status_code in (400, 422)

    # 2. End date before start date
    res = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Inverted Dates Campaign",
            "start_date": (now + timedelta(days=5)).isoformat(),
            "end_date": (now - timedelta(days=1)).isoformat(),
        },
        headers=headers,
    )
    assert res.status_code in (400, 422)


def test_campaign_list_and_filters(client, db_session):
    """Verify listing campaigns with status and platform filtering."""
    user_id, headers = _register(client, "camp_lister@example.com", "Campaign Lister")

    # Create 3 campaigns
    c1 = client.post("/api/v1/campaigns", json={"name": "Twitter Launch", "platform": "twitter", "status": "active"}, headers=headers).json()
    c2 = client.post("/api/v1/campaigns", json={"name": "Instagram Stories", "platform": "instagram", "status": "active"}, headers=headers).json()
    c3 = client.post("/api/v1/campaigns", json={"name": "LinkedIn B2B", "platform": "linkedin", "status": "completed"}, headers=headers).json()

    # List all
    res = client.get("/api/v1/campaigns", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 3

    # Filter by status
    res = client.get("/api/v1/campaigns?status=active", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # Filter by platform
    res = client.get("/api/v1/campaigns?platform=linkedin", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["name"] == "LinkedIn B2B"


def test_campaign_update_and_delete(client, db_session):
    """Verify updating campaign fields and deleting campaign."""
    user_id, headers = _register(client, "camp_upd@example.com", "Camp Updater")

    c = client.post(
        "/api/v1/campaigns",
        json={"name": "Draft Campaign", "budget": 1000.0, "status": "draft"},
        headers=headers,
    ).json()
    camp_id = c["id"]

    # Update
    upd_res = client.put(
        f"/api/v1/campaigns/{camp_id}",
        json={"name": "Published Campaign", "budget": 2500.0, "status": "active", "revenue": 6000.0},
        headers=headers,
    )
    assert upd_res.status_code == 200
    assert upd_res.json()["name"] == "Published Campaign"
    assert upd_res.json()["budget"] == 2500.0
    assert upd_res.json()["status"] == "active"
    assert upd_res.json()["revenue"] == 6000.0

    # Delete
    del_res = client.delete(f"/api/v1/campaigns/{camp_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify not found
    get_res = client.get(f"/api/v1/campaigns/{camp_id}", headers=headers)
    assert get_res.status_code == 404


def test_campaign_user_isolation(client, db_session):
    """Verify user A cannot view, update, or delete user B's campaign."""
    user_a, headers_a = _register(client, "user_a@example.com", "User A")
    user_b, headers_b = _register(client, "user_b@example.com", "User B")

    camp_a = client.post(
        "/api/v1/campaigns",
        json={"name": "Secret Campaign User A"},
        headers=headers_a,
    ).json()
    camp_id = camp_a["id"]

    # User B tries to get User A's campaign
    res = client.get(f"/api/v1/campaigns/{camp_id}", headers=headers_b)
    assert res.status_code in (403, 404)

    # User B tries to update User A's campaign
    res = client.put(f"/api/v1/campaigns/{camp_id}", json={"name": "Hacked"}, headers=headers_b)
    assert res.status_code in (403, 404)

    # User B tries to delete User A's campaign
    res = client.delete(f"/api/v1/campaigns/{camp_id}", headers=headers_b)
    assert res.status_code in (403, 404)


# ===========================================================================
# 2. CAMPAIGN ↔ POST ASSOCIATION & TRACKING TESTS
# ===========================================================================

def test_campaign_post_association_and_tracking(client, db_session):
    """Test attaching posts to campaign, tracking stats breakdown and progress."""
    user_id, headers = _register(client, "camp_posts@example.com", "Camp Posts Tester")
    acc = _create_social_account(db_session, user_id, "x", "TweetDesk")

    # 1. Create campaign
    camp = client.post(
        "/api/v1/campaigns",
        json={"name": "Brand Awareness 2026", "budget": 3000.0, "status": "active"},
        headers=headers,
    ).json()
    camp_id = camp["id"]

    # 2. Create post directly with campaign_id
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    p1 = client.post(
        "/api/v1/posts",
        json={
            "content": "Campaign kickoff post! #Brand2026",
            "post_type": "text",
            "status": "scheduled",
            "scheduled_at": future_time,
            "social_account_ids": [acc.id],
            "campaign_id": camp_id,
        },
        headers=headers,
    ).json()

    # 3. Create draft post without campaign, then attach via campaign posts endpoint
    p2 = client.post(
        "/api/v1/posts",
        json={
            "content": "Draft product teaser for campaign",
            "post_type": "text",
            "status": "draft",
            "social_account_ids": [acc.id],
        },
        headers=headers,
    ).json()

    # Bulk attach p2 to campaign
    attach_res = client.post(
        f"/api/v1/campaigns/{camp_id}/posts",
        json={"post_ids": [p2["id"]]},
        headers=headers,
    )
    assert attach_res.status_code == 200

    # 4. Fetch campaign details to verify tracking statistics
    camp_detail = client.get(f"/api/v1/campaigns/{camp_id}", headers=headers).json()
    stats = camp_detail["tracking_stats"]
    assert stats["total_posts"] == 2
    assert stats["scheduled_posts"] == 1
    assert stats["draft_posts"] == 1
    assert stats["published_posts"] == 0
    assert stats["progress_percentage"] == 0.0

    # 5. Fetch campaign posts list
    posts_res = client.get(f"/api/v1/campaigns/{camp_id}/posts", headers=headers)
    assert posts_res.status_code == 200
    assert posts_res.json()["total"] == 2

    # 6. Detach p2 from campaign
    detach_res = client.delete(f"/api/v1/campaigns/{camp_id}/posts/{p2['id']}", headers=headers)
    assert detach_res.status_code == 200

    # Verify tracking stats updated
    camp_detail_after = client.get(f"/api/v1/campaigns/{camp_id}", headers=headers).json()
    assert camp_detail_after["tracking_stats"]["total_posts"] == 1


def test_cross_user_post_attachment_rejected(client, db_session):
    """Verify user A cannot attach user B's posts to user A's campaign."""
    user_a, headers_a = _register(client, "user_att_a@example.com", "Attacher A")
    user_b, headers_b = _register(client, "user_att_b@example.com", "Attacher B")

    camp_a = client.post("/api/v1/campaigns", json={"name": "Campaign A"}, headers=headers_a).json()
    post_b = client.post(
        "/api/v1/posts",
        json={"content": "User B's draft", "status": "draft"},
        headers=headers_b,
    ).json()

    # User A tries to attach User B's post
    res = client.post(
        f"/api/v1/campaigns/{camp_a['id']}/posts",
        json={"post_ids": [post_b["id"]]},
        headers=headers_a,
    )
    assert res.status_code in (400, 403, 404)


# ===========================================================================
# 3. REAL ANALYTICS & HONEST ROI TESTS
# ===========================================================================

def test_record_post_metrics_and_content_analytics(client, db_session):
    """Verify recording real metrics on a post and querying aggregated content analytics."""
    user_id, headers = _register(client, "analytics_user@example.com", "Analytics User")
    acc = _create_social_account(db_session, user_id, "x", "AnalyticsBot")

    # 1. Create a published post
    post = Post(
        user_id=user_id,
        content="Viral announcement post about our new release!",
        post_type="text",
        status=PostStatus.published.value,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    # Link to social account
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    # 2. Record metrics
    metric_payload = {
        "post_id": post.id,
        "social_account_id": acc.id,
        "platform": "x",
        "impressions": 3000,
        "likes": 180,
        "comments": 45,
        "shares": 30,
        "clicks": 95,
        "reach": 2800,
    }
    m_res = client.post("/api/v1/analytics/metrics", json=metric_payload, headers=headers)
    assert m_res.status_code == 201, m_res.text
    m_data = m_res.json()
    assert m_data["likes"] == 180
    assert m_data["clicks"] == 95

    # 3. Query Content Analytics
    res = client.get("/api/v1/analytics/content", headers=headers)
    assert res.status_code == 200
    c_data = res.json()
    assert c_data["overview"]["total_posts"] == 1
    assert c_data["overview"]["published_posts"] == 1
    assert c_data["overview"]["total_likes"] == 180
    assert c_data["overview"]["total_comments"] == 45
    assert c_data["overview"]["total_clicks"] == 95
    assert c_data["overview"]["total_impressions"] == 3000
    assert len(c_data["by_platform"]) >= 1
    assert len(c_data["top_posts"]) == 1
    assert c_data["top_posts"][0]["likes"] == 180


def test_audience_analytics(client, db_session):
    """Verify audience analytics accurately returns real connected accounts data."""
    user_id, headers = _register(client, "audience_user@example.com", "Audience User")
    _create_social_account(db_session, user_id, "facebook", "FB_Profile")
    _create_social_account(db_session, user_id, "linkedin", "LI_Profile")

    res = client.get("/api/v1/analytics/audience", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_connected_accounts"] == 2
    assert data["active_accounts"] == 2
    assert len(data["by_account"]) == 2
    assert "unavailable_metrics" in data
    assert "demographics" in data["unavailable_metrics"][0]


def test_campaign_analytics_and_honest_roi(client, db_session):
    """Verify campaign performance tracking and honest ROI calculation."""
    user_id, headers = _register(client, "roi_user@example.com", "ROI Tester")
    acc = _create_social_account(db_session, user_id, "instagram", "InstaBrand")

    # Campaign 1: Has revenue tracked ($1000 budget, $3500 revenue -> ROI = 250%)
    c1 = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Summer Sale 2026",
            "budget": 1000.0,
            "revenue": 3500.0,
            "conversions": 70,
            "status": "active",
        },
        headers=headers,
    ).json()

    # Campaign 2: No revenue tracked -> roi_available should be False
    c2 = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Organic Community Growth",
            "budget": 500.0,
            "revenue": None,
            "conversions": 15,
            "status": "active",
        },
        headers=headers,
    ).json()

    # Attach post with metrics to Campaign 1
    post1 = Post(
        user_id=user_id,
        campaign_id=c1["id"],
        content="Summer sale 50% discount on all items!",
        post_type="image",
        status=PostStatus.published.value,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(post1)
    db_session.commit()
    db_session.refresh(post1)

    metric1 = PostMetric(
        post_id=post1.id,
        social_account_id=acc.id,
        platform="instagram",
        impressions=10000,
        reach=8500,
        likes=500,
        comments=60,
        shares=40,
        clicks=250,
        engagement=850,
    )
    db_session.add(metric1)
    db_session.commit()

    # Fetch Campaign Analytics
    res = client.get("/api/v1/analytics/campaigns", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["overview"]["total_campaigns"] == 2

    camp1_summary = next(c for c in data["campaigns"] if c["campaign_id"] == c1["id"])
    assert camp1_summary["roi_available"] is True
    assert camp1_summary["roi_percentage"] == 250.0
    assert camp1_summary["total_clicks"] == 250
    assert camp1_summary["cpc"] == 4.0  # $1000 / 250 clicks = $4.00
    assert camp1_summary["cpa"] == 14.29  # $1000 / 70 conversions = $14.29
    assert camp1_summary["ctr"] == 2.5  # (250 / 10000) * 100 = 2.5%

    camp2_summary = next(c for c in data["campaigns"] if c["campaign_id"] == c2["id"])
    assert camp2_summary["roi_available"] is False
    assert camp2_summary["roi_percentage"] is None


def test_campaign_comparison_and_winner_selection(client, db_session):
    """Verify side-by-side comparison of campaigns and metric matrix."""
    user_id, headers = _register(client, "compare_user@example.com", "Comparator")

    c1 = client.post(
        "/api/v1/campaigns",
        json={"name": "Campaign Alpha", "budget": 1000.0, "revenue": 2000.0, "conversions": 50},
        headers=headers,
    ).json()

    c2 = client.post(
        "/api/v1/campaigns",
        json={"name": "Campaign Beta", "budget": 1500.0, "revenue": 4500.0, "conversions": 90},
        headers=headers,
    ).json()

    payload = {"campaign_ids": [c1["id"], c2["id"]]}
    res = client.post("/api/v1/analytics/comparison", json=payload, headers=headers)
    assert res.status_code == 200
    comp_data = res.json()
    assert len(comp_data["compared_campaigns"]) == 2
    assert "comparison_matrix" in comp_data
    assert comp_data["winner_by_roi"]["campaign_id"] == c2["id"]
    assert comp_data["winner_by_roi"]["roi_percentage"] == 200.0  # (4500-1500)/1500 * 100


def test_analytics_export_csv_and_json(client, db_session):
    """Verify CSV and JSON report export endpoints."""
    user_id, headers = _register(client, "export_user@example.com", "Exporter")
    client.post("/api/v1/campaigns", json={"name": "Exportable Campaign", "budget": 500.0}, headers=headers)

    # 1. Export CSV
    csv_res = client.get("/api/v1/analytics/export?format=csv", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "Exportable Campaign" in csv_res.text

    # 2. Export JSON
    json_res = client.get("/api/v1/analytics/export?format=json", headers=headers)
    assert json_res.status_code == 200
    j_data = json_res.json()
    assert "content" in j_data
    assert "campaigns" in j_data
