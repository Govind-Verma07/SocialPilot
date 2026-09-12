"""
tests/test_phase5_publishing.py
--------------------------------
Automated test suite for Phase 5: Actual Social Media Publishing.

Covers:
1. LinkedIn Successful publish
2. LinkedIn Invalid/missing token
3. LinkedIn API failure (e.g. 403 / 500)
4. Ownership protection (user B cannot publish user A's post)
5. Unauthorized request (no JWT token)
6. Multiple selected accounts
7. One platform succeeds while another fails (partial success)
8. Correct per-platform result recording
9. Successful publish updates Post status to 'published'
10. Failed publish updates Post status to 'failed'
"""

from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta
import httpx

from app.models.enums import PostStatus, SocialPlatform, AccountStatus
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.core.encryption import encrypt_token


def _register_and_login(client, email: str, name: str = "Test User") -> tuple[str, str, dict]:
    """Helper to register and return (user_id, token, auth_headers)."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": "Password123",
        },
    )
    assert res.status_code == 201
    data = res.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, token, headers


def _seed_account(db_session, user_id: str, platform: SocialPlatform, name: str, token: str = "mock-secret-token") -> SocialAccount:
    """Helper to create a connected social account in DB."""
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_acc_{user_id[:6]}",
        account_name=name,
        account_username=f"{platform.value}_handle",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token(token) if token else None,
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


# ==============================================================================
# TEST 1 — LinkedIn Successful Publish
# ==============================================================================
def test_1_linkedin_successful_publish(client, db_session):
    user_id, token, headers = _register_and_login(client, "user_li_success@test.com", "LinkedIn User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn")

    post = Post(
        user_id=user_id,
        content="Exciting updates from SocialPilot! #launch",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    mock_resp = httpx.Response(
        201,
        json={"id": "urn:li:share:987654321"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == PostStatus.published.value
    assert data["published_at"] is not None
    assert len(data["publish_results"]) == 1

    pr = data["publish_results"][0]
    assert pr["platform"] == "linkedin"
    assert pr["status"] == "published"
    assert pr["platform_post_id"] == "urn:li:share:987654321"
    assert "https://www.linkedin.com/feed/update/urn:li:share:987654321" in pr["published_url"]


# ==============================================================================
# TEST 2 — LinkedIn Missing / Invalid Token
# ==============================================================================
def test_2_linkedin_missing_token(client, db_session):
    user_id, token, headers = _register_and_login(client, "user_li_notoken@test.com", "No Token User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn", token=None)

    post = Post(
        user_id=user_id,
        content="Post without valid token",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == PostStatus.failed.value
    assert len(data["publish_results"]) == 1
    assert data["publish_results"][0]["status"] == "failed"
    assert "token is missing or invalid" in data["publish_results"][0]["error_message"]


# ==============================================================================
# TEST 3 — LinkedIn API Failure (403 Forbidden)
# ==============================================================================
def test_3_linkedin_api_failure(client, db_session):
    user_id, token, headers = _register_and_login(client, "user_li_fail@test.com", "API Fail User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn")

    post = Post(
        user_id=user_id,
        content="Post encountering 403 API error",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc.id))
    db_session.commit()

    mock_resp = httpx.Response(
        403,
        json={"message": "Not enough permissions to access /ugcPosts"},
        request=httpx.Request("POST", "https://api.linkedin.com/v2/ugcPosts"),
    )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == PostStatus.failed.value
    assert len(data["publish_results"]) == 1
    assert data["publish_results"][0]["status"] == "failed"
    assert "permission denied (403)" in data["publish_results"][0]["error_message"]


# ==============================================================================
# TEST 4 — Ownership Protection (User B cannot publish User A's post)
# ==============================================================================
def test_4_ownership_protection(client, db_session):
    user_a_id, _, headers_a = _register_and_login(client, "user_a_p5@test.com", "User A")
    user_b_id, _, headers_b = _register_and_login(client, "user_b_p5@test.com", "User B")
    acc_a = _seed_account(db_session, user_a_id, SocialPlatform.linkedin, "User A LinkedIn")

    post = Post(
        user_id=user_a_id,
        content="User A private post",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=acc_a.id))
    db_session.commit()

    # User B tries to publish User A's post
    res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers_b)
    assert res.status_code == 403
    assert "permission" in res.json()["detail"].lower()


# ==============================================================================
# TEST 5 — Unauthorized Request (No JWT)
# ==============================================================================
def test_5_unauthorized_request(client, db_session):
    user_id, _, _ = _register_and_login(client, "user_unauth_p5@test.com", "Unauth User")
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "User LinkedIn")

    post = Post(
        user_id=user_id,
        content="Post without JWT",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.commit()

    res = client.post(f"/api/v1/posts/{post.id}/publish")
    assert res.status_code == 401


# ==============================================================================
# TEST 6, 7, 8 — Multi-Account Publishing: Partial Success (LinkedIn ok, Facebook fail)
# ==============================================================================
def test_6_multi_platform_partial_success(client, db_session):
    user_id, _, headers = _register_and_login(client, "user_multi_p5@test.com", "Multi User")
    li_acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn")
    fb_acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "My Facebook")

    post = Post(
        user_id=user_id,
        content="Cross-platform test post",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=li_acc.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=fb_acc.id))
    db_session.commit()

    async def mock_post_call(url, *args, **kwargs):
        if "linkedin" in str(url):
            return httpx.Response(
                201,
                json={"id": "urn:li:share:111222"},
                request=httpx.Request("POST", str(url)),
            )
        else:
            return httpx.Response(
                400,
                json={"error": {"message": "Invalid page token"}},
                request=httpx.Request("POST", str(url)),
            )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, side_effect=mock_post_call):
        res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == PostStatus.published.value
    assert len(data["publish_results"]) == 2

    li_res = next(r for r in data["publish_results"] if r["platform"] == "linkedin")
    fb_res = next(r for r in data["publish_results"] if r["platform"] == "facebook")

    assert li_res["status"] == "published"
    assert li_res["platform_post_id"] == "urn:li:share:111222"

    assert fb_res["status"] == "failed"
    assert "Invalid page token" in fb_res["error_message"]


# ==============================================================================
# TEST 9 — Multi-Platform All Success -> Published Status
# ==============================================================================
def test_9_multi_platform_all_success(client, db_session):
    user_id, _, headers = _register_and_login(client, "user_all_win@test.com", "Win User")
    li_acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn")
    x_acc = _seed_account(db_session, user_id, SocialPlatform.x, "My X")

    post = Post(
        user_id=user_id,
        content="Success across all channels!",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=li_acc.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=x_acc.id))
    db_session.commit()

    async def mock_post_call(url, *args, **kwargs):
        if "linkedin" in str(url):
            return httpx.Response(
                201,
                json={"id": "urn:li:share:333444"},
                request=httpx.Request("POST", str(url)),
            )
        else:
            return httpx.Response(
                201,
                json={"data": {"id": "18273645"}},
                request=httpx.Request("POST", str(url)),
            )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, side_effect=mock_post_call):
        res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == PostStatus.published.value
    assert len(data["publish_results"]) == 2
    assert all(r["status"] == "published" for r in data["publish_results"])


# ==============================================================================
# TEST 10 — Multi-Platform All Fail -> Failed Status
# ==============================================================================
def test_10_multi_platform_all_fail(client, db_session):
    user_id, _, headers = _register_and_login(client, "user_all_fail@test.com", "Fail User")
    li_acc = _seed_account(db_session, user_id, SocialPlatform.linkedin, "My LinkedIn")
    x_acc = _seed_account(db_session, user_id, SocialPlatform.x, "My X")

    post = Post(
        user_id=user_id,
        content="Post destined to fail",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.flush()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=li_acc.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=x_acc.id))
    db_session.commit()

    async def mock_post_call(url, *args, **kwargs):
        return httpx.Response(
            500,
            json={"error": "Platform server failure"},
            request=httpx.Request("POST", str(url)),
        )

    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, side_effect=mock_post_call):
        res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == PostStatus.failed.value
    assert len(data["publish_results"]) == 2
    assert all(r["status"] == "failed" for r in data["publish_results"])
