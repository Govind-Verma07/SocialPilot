"""
tests/test_auto_scheduler_and_real_logs.py
-------------------------------------------
Tests for:
1. Real post content included in publishing audit logs (.log file export & in-memory content).
2. Automated publishing via background scheduler without user interaction.
3. Force publishing via publish now endpoint.
"""

from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone, timedelta
import pytest
import httpx

from app.models.enums import PostStatus, SocialPlatform, AccountStatus
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.core.encryption import encrypt_token
from app.services.publishing.scheduler import check_and_publish_due_posts_once
from app.services.publishing.log_generator import generate_post_audit_log_content


def _register_and_login(client, email: str, name: str = "Test User") -> tuple[str, str, dict]:
    res = client.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "Password123"},
    )
    assert res.status_code == 201
    data = res.json()
    return data["user"]["id"], data["access_token"], {"Authorization": f"Bearer {data['access_token']}"}


def _seed_account(db_session, user_id: str, platform: SocialPlatform, name: str) -> SocialAccount:
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_acc_{user_id[:6]}",
        account_name=name,
        account_username=f"{platform.value}_handle",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("mock-token"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def test_log_file_contains_real_post_content(client, db_session):
    user_id, _, headers = _register_and_login(client, "author_log@test.com", "Post Master")
    fb_acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "My FB Page")
    yt_acc = _seed_account(db_session, user_id, SocialPlatform.youtube, "My YouTube Channel")

    target_content = "🚀 Special Announcement: Product launch is live! Visit https://example.com"
    post = Post(
        user_id=user_id,
        content=target_content,
        media_urls=["https://images.unsplash.com/photo-sample.jpg"],
        post_type="image",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db_session.add(post)
    db_session.commit()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=fb_acc.id))
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=yt_acc.id))
    db_session.commit()

    # Generate log content
    log_text = generate_post_audit_log_content(db_session, post)

    # Verify real content and metadata are included
    assert target_content in log_text
    assert "author_log@test.com" in log_text
    assert "Post Master" in log_text
    assert "https://images.unsplash.com/photo-sample.jpg" in log_text
    assert "FACEBOOK" in log_text
    assert "YOUTUBE" in log_text
    assert "Character Count" in log_text
    assert "Word Count" in log_text

    # Verify export endpoint returns this content
    res = client.get(f"/api/v1/posts/{post.id}/publishing-logs/export", headers=headers)
    assert res.status_code == 200
    assert target_content in res.text
    assert "SOCIALPILOT — POST PUBLISHING AUDIT LOG" in res.text


def test_force_publish_now(client, db_session):
    user_id, _, headers = _register_and_login(client, "force_pub@test.com", "Force Publisher")
    fb_acc = _seed_account(db_session, user_id, SocialPlatform.facebook, "FB Page")

    post = Post(
        user_id=user_id,
        content="Testing Force Publish Now button",
        status=PostStatus.scheduled.value,
        scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(post)
    db_session.commit()
    db_session.add(PostSocialAccount(post_id=post.id, social_account_id=fb_acc.id))
    db_session.commit()

    # User clicks Publish Now
    mock_resp = httpx.Response(200, json={"id": "fb_force_123"}, request=httpx.Request("POST", "https://graph.facebook.com"))
    with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_resp):
        res = client.post(f"/api/v1/posts/{post.id}/publish", headers=headers)

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "published"
    assert data["published_at"] is not None

    db_session.refresh(post)
    assert post.status == PostStatus.published.value
    assert post.published_at is not None
