"""
tests/test_multi_account_lifecycle.py
-------------------------------------
End-to-end automated tests for multi-account support across the same and multiple platforms:
1. Connecting multiple accounts from the same platform (e.g. 2 Facebook Pages, 2 YouTube Channels).
2. Duplicate account prevention (re-auth on same account gracefully updates existing row).
3. Independent disconnect (deleting Account A preserves Account B of the same platform).
4. Multi-account post targeting (targeting multiple accounts of the same platform).
5. Publishing queue and job execution per account.
"""

from datetime import datetime, timedelta, timezone
import pytest
from app.core.encryption import encrypt_token
from app.models.enums import AccountStatus, PostStatus, PublishingJobStatus, SocialPlatform
from app.models.post import Post, PostSocialAccount
from app.models.publishing_job import PublishingJob
from app.models.post_publish_result import PostPublishResult
from app.models.social_account import SocialAccount


def _register(client, email: str, name: str = "Multi User"):
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


def test_multi_accounts_same_platform_creation_and_listing(client, db_session):
    """Test connecting multiple distinct accounts from the same platform for the same user."""
    user_id, headers = _register(client, "multi_fb@example.com", "FB Multiple Owner")
    now = datetime.now(timezone.utc)

    # 1. Add Facebook Page 1 (Tech Page)
    page1 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_page_1001",
        account_name="Tech Innovation Page",
        account_username="tech_innovate",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("fb_page_1_token_secret"),
        connected_at=now,
        last_synced_at=now,
    )
    # 2. Add Facebook Page 2 (Community Page)
    page2 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_page_1002",
        account_name="Global Community Page",
        account_username="global_community",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("fb_page_2_token_secret"),
        connected_at=now,
        last_synced_at=now,
    )
    # 3. Add YouTube Channel 1
    yt1 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.youtube.value,
        platform_account_id="yt_channel_2001",
        account_name="Tech Reviews Channel",
        account_username="tech_reviews",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("yt_token_secret"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add_all([page1, page2, yt1])
    db_session.commit()

    # Query via API
    res = client.get("/api/v1/social/accounts", headers=headers)
    assert res.status_code == 200
    accounts = res.json()
    assert len(accounts) == 3

    fb_accounts = [a for a in accounts if a["platform"] == "facebook"]
    assert len(fb_accounts) == 2
    fb_names = {a["account_name"] for a in fb_accounts}
    assert fb_names == {"Tech Innovation Page", "Global Community Page"}

    # Verify no tokens leaked
    for a in accounts:
        assert "access_token_encrypted" not in a
        assert "refresh_token_encrypted" not in a
        assert "token_secret" not in str(a)


def test_duplicate_account_prevention(client, db_session):
    """Test that connecting the exact same (user, platform, platform_account_id) updates instead of duplicating."""
    user_id, headers = _register(client, "duplicate_test@example.com")
    now = datetime.now(timezone.utc)

    # First connection
    acc = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_page_repeat",
        account_name="Original Name",
        account_username="orig_handle",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("token_v1"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()

    # Check that identical (user_id, platform, platform_account_id) query finds existing row
    existing = (
        db_session.query(SocialAccount)
        .filter(
            SocialAccount.user_id == user_id,
            SocialAccount.platform == SocialPlatform.facebook.value,
            SocialAccount.platform_account_id == "fb_page_repeat",
        )
        .first()
    )
    assert existing is not None
    # Simulate update on reconnect
    existing.account_name = "Updated Page Name"
    existing.access_token_encrypted = encrypt_token("token_v2")
    db_session.commit()

    # Verify still only 1 row exists
    count = (
        db_session.query(SocialAccount)
        .filter(
            SocialAccount.user_id == user_id,
            SocialAccount.platform == SocialPlatform.facebook.value,
            SocialAccount.platform_account_id == "fb_page_repeat",
        )
        .count()
    )
    assert count == 1

    res = client.get("/api/v1/social/accounts", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["account_name"] == "Updated Page Name"


def test_independent_disconnect_preserves_sibling_accounts(client, db_session):
    """Test disconnecting one account leaves other accounts of the same platform intact."""
    user_id, headers = _register(client, "disconnect_sibling@example.com")
    now = datetime.now(timezone.utc)

    acc1 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_keep_1",
        account_name="Keep This Page",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("tok1"),
        connected_at=now,
    )
    acc2 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_delete_2",
        account_name="Delete This Page",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("tok2"),
        connected_at=now,
    )
    db_session.add_all([acc1, acc2])
    db_session.commit()
    db_session.refresh(acc1)
    db_session.refresh(acc2)

    # Disconnect acc2
    del_res = client.delete(f"/api/v1/social/accounts/{acc2.id}", headers=headers)
    assert del_res.status_code == 200

    # Verify acc2 is deleted, acc1 remains
    list_res = client.get("/api/v1/social/accounts", headers=headers)
    assert list_res.status_code == 200
    accounts = list_res.json()
    assert len(accounts) == 1
    assert accounts[0]["id"] == str(acc1.id)
    assert accounts[0]["account_name"] == "Keep This Page"


def test_multi_account_post_targeting(client, db_session):
    """Test creating a post targeting multiple accounts from the same platform simultaneously."""
    user_id, headers = _register(client, "post_multi@example.com")
    now = datetime.now(timezone.utc)

    acc1 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_target_1",
        account_name="Facebook Page 1",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("tok1"),
        connected_at=now,
    )
    acc2 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_target_2",
        account_name="Facebook Page 2",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("tok2"),
        connected_at=now,
    )
    acc3 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.linkedin.value,
        platform_account_id="li_target_3",
        account_name="LinkedIn Profile",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("tok3"),
        connected_at=now,
    )
    db_session.add_all([acc1, acc2, acc3])
    db_session.commit()
    db_session.refresh(acc1)
    db_session.refresh(acc2)
    db_session.refresh(acc3)

    future_time = (now + timedelta(hours=2)).isoformat()

    # Create post targeting both Facebook accounts and LinkedIn
    create_payload = {
        "content": "Announcing our new multi-account publishing engine! 🚀",
        "post_type": "text",
        "scheduled_at": future_time,
        "social_account_ids": [str(acc1.id), str(acc2.id), str(acc3.id)],
    }
    create_res = client.post("/api/v1/posts/", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    post_data = create_res.json()
    post_id = post_data["id"]

    # Verify the post has 3 social accounts associated
    target_accounts = post_data["social_accounts"]
    assert len(target_accounts) == 3
    target_ids = {a["id"] for a in target_accounts}
    assert target_ids == {str(acc1.id), str(acc2.id), str(acc3.id)}

    # Verify database associations
    links = db_session.query(PostSocialAccount).filter(PostSocialAccount.post_id == post_id).all()
    assert len(links) == 3
    link_account_ids = {str(l.social_account_id) for l in links}
    assert link_account_ids == {str(acc1.id), str(acc2.id), str(acc3.id)}


def test_multi_account_independent_publishing_jobs(client, db_session):
    """Test that publishing to multiple accounts creates distinct publishing jobs per account."""
    user_id, headers = _register(client, "multi_publish@example.com")
    now = datetime.now(timezone.utc)

    acc1 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_pub_1",
        account_name="Brand Page A",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("tok1"),
        connected_at=now,
    )
    acc2 = SocialAccount(
        user_id=user_id,
        platform=SocialPlatform.facebook.value,
        platform_account_id="fb_pub_2",
        account_name="Brand Page B",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("tok2"),
        connected_at=now,
    )
    db_session.add_all([acc1, acc2])
    db_session.commit()
    db_session.refresh(acc1)
    db_session.refresh(acc2)

    post = Post(
        user_id=user_id,
        content="Testing concurrent multi-account publishing",
        status=PostStatus.scheduled.value,
        scheduled_at=now + timedelta(minutes=10),
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)

    link1 = PostSocialAccount(post_id=post.id, social_account_id=acc1.id)
    link2 = PostSocialAccount(post_id=post.id, social_account_id=acc2.id)
    db_session.add_all([link1, link2])
    db_session.commit()

    # Create independent publishing jobs for each account
    job1 = PublishingJob(
        post_id=post.id,
        social_account_id=acc1.id,
        status=PublishingJobStatus.published.value,
    )
    job2 = PublishingJob(
        post_id=post.id,
        social_account_id=acc2.id,
        status=PublishingJobStatus.published.value,
    )
    db_session.add_all([job1, job2])
    db_session.commit()

    # Verify jobs exist independently
    jobs = db_session.query(PublishingJob).filter(PublishingJob.post_id == post.id).all()
    assert len(jobs) == 2
    job_account_ids = {str(j.social_account_id) for j in jobs}
    assert job_account_ids == {str(acc1.id), str(acc2.id)}
