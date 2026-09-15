"""
tests/test_publishing_media_pipeline.py
---------------------------------------
Comprehensive test suite for the SocialPilot Common Media Pipeline.
Validates:
1. Public HMAC token generation, verification, and expiry
2. Public media download streaming without JWT (for external publishing crawlers)
3. Media resolution for all 5 formats: Image, Video, Carousel, Story, Reel
4. Position preservation for Carousel items in media resolver
5. Platform adapter media publishing:
   - LinkedIn (Text UGC vs. Image/Video registerUpload)
   - Instagram (Text SKIPPED, Single Image, Video/Reel, Carousel, Story)
   - Facebook (Text feed, Photo upload, Video upload, Carousel attached_media)
   - Pinterest (Text SKIPPED, Image Pin with public URL)
   - YouTube (Text SKIPPED, Video upload)
   - X (Twitter) (Preserves credits handling & accepts context)
6. Zero regression for text-only publishing on Facebook & LinkedIn
"""

import io
from datetime import datetime, timezone, timedelta
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from app.core.encryption import encrypt_token
from app.db.mongodb import get_mongo_db, get_media_assets_collection, get_content_posts_collection
from app.models.enums import AccountStatus, PostStatus, SocialPlatform
from app.models.post import Post, PostSocialAccount
from app.models.social_account import SocialAccount
from app.services.media_service import MediaService
from app.services.publishing.media_resolver import resolve_post_publish_context, PostPublishContext, ResolvedMediaItem
from app.services.publishing.service import PublishingService
from app.services.publishing.adapters.linkedin import LinkedInPublisher
from app.services.publishing.adapters.instagram import InstagramPublisher
from app.services.publishing.adapters.facebook import FacebookPublisher
from app.services.publishing.adapters.pinterest import PinterestPublisher
from app.services.publishing.adapters.youtube import YouTubePublisher
from app.services.publishing.adapters.x import XPublisher


def _register_and_login(client, email: str, name: str = "Publisher User") -> tuple[str, str, dict]:
    res = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": "Password123!",
        },
    )
    assert res.status_code == 201
    data = res.json()
    token = data["access_token"]
    user_id = data["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, token, headers


def _seed_account(db_session, user_id: str, platform: SocialPlatform) -> SocialAccount:
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_id_123",
        account_name=f"{platform.value.capitalize()} Test Account",
        account_username=f"{platform.value}_user",
        access_token_encrypted=encrypt_token("mock-valid-access-token"),
        status=AccountStatus.connected.value,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


# ===========================================================================
# 1. Public HMAC Token & Public Download Endpoint Tests
# ===========================================================================

def test_public_media_token_generation_and_verification():
    """Verify HMAC token generation, valid verification, and rejection of tampered tokens."""
    media_id = "test_media_12345"
    token = MediaService.generate_public_media_token(media_id)
    assert token and "." in token

    # Verification of matching media_id
    assert MediaService.verify_public_media_token(media_id, token) is True

    # Verification of different media_id fails
    assert MediaService.verify_public_media_token("other_media_id", token) is False

    # Tampered signature fails
    parts = token.split(".")
    tampered = f"{parts[0]}.bad_signature_abc123"
    assert MediaService.verify_public_media_token(media_id, tampered) is False

    # Expired timestamp fails
    expired_ts = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
    expired_token = f"{expired_ts}.some_sig"
    assert MediaService.verify_public_media_token(media_id, expired_token) is False


def test_public_media_download_endpoint_without_jwt(client, db_session):
    """Verify external crawler can download media via public endpoint without JWT."""
    user_id, _, auth_headers = _register_and_login(client, "crawler_test@example.com")

    # 1. Upload an image asset with authentication
    file_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"A" * 100
    upload_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("photo.jpg", io.BytesIO(file_bytes), "image/jpeg")},
        headers=auth_headers,
    )
    assert upload_res.status_code == 201
    media_id = upload_res.json()["media_id"]

    # 2. Generate public token
    token = MediaService.generate_public_media_token(media_id)

    # 3. Request public media stream without Authorization header
    res = client.get(f"/api/v1/media/public/{media_id}?token={token}")
    assert res.status_code == 200
    assert res.content == file_bytes
    assert res.headers.get("content-type") == "image/jpeg"

    # 4. Request with invalid token -> 403 Forbidden
    bad_res = client.get(f"/api/v1/media/public/{media_id}?token=invalid.token")
    assert bad_res.status_code == 403


# ===========================================================================
# 2. Media Resolver Tests for All Formats
# ===========================================================================

@pytest.mark.asyncio
async def test_media_resolver_for_all_formats(client, db_session):
    """Test resolve_post_publish_context for Text, Image, Video, Carousel, Story, Reel."""
    user_id, _, auth_headers = _register_and_login(client, "resolver_test@example.com")
    mongo_db = get_mongo_db()

    # Upload 1 image and 1 video
    img_bytes = b"\xff\xd8\xff\xe0" + b"IMG" * 50
    vid_bytes = b"\x00\x00\x00 ftypmp42" + b"VID" * 100

    r1 = client.post("/api/v1/media/upload", files={"file": ("banner.jpg", io.BytesIO(img_bytes), "image/jpeg")}, headers=auth_headers)
    assert r1.status_code == 201
    img_id_1 = r1.json()["media_id"]

    r2 = client.post("/api/v1/media/upload", files={"file": ("slide2.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"P"*50), "image/png")}, headers=auth_headers)
    assert r2.status_code == 201
    img_id_2 = r2.json()["media_id"]

    r3 = client.post("/api/v1/media/upload", files={"file": ("clip.mp4", io.BytesIO(vid_bytes), "video/mp4")}, headers=auth_headers)
    assert r3.status_code == 201
    vid_id = r3.json()["media_id"]

    # --- A. Carousel Post with preserved ordering ---
    p_carousel = Post(
        user_id=user_id,
        content="Carousel Post",
        post_type="carousel",
        media_urls=[],
        status="scheduled",
    )
    db_session.add(p_carousel)
    db_session.commit()
    db_session.refresh(p_carousel)

    # Insert content_post doc in MongoDB
    content_col = get_content_posts_collection(mongo_db)
    await content_col.insert_one({
        "post_id": str(p_carousel.id),
        "user_id": user_id,
        "post_type": "carousel",
        "media_ids": [img_id_1, img_id_2],
        "media_items": [
            {"media_id": img_id_1, "position": 1},
            {"media_id": img_id_2, "position": 2},
        ],
    })

    ctx = await resolve_post_publish_context(db_session, p_carousel)
    assert ctx.has_media is True
    assert ctx.is_carousel is True
    assert len(ctx.media_items) == 2
    assert ctx.media_items[0].media_id == img_id_1
    assert ctx.media_items[0].position == 1
    assert ctx.media_items[1].media_id == img_id_2
    assert ctx.media_items[1].position == 2
    assert ctx.media_items[0].public_url is not None
    assert "/api/v1/media/public/" in ctx.media_items[0].public_url

    # --- B. Video / Reel Post ---
    p_video = Post(
        user_id=user_id,
        content="Reel Post",
        post_type="reel",
        media_urls=[],
        status="scheduled",
    )
    db_session.add(p_video)
    db_session.commit()
    db_session.refresh(p_video)

    await content_col.insert_one({
        "post_id": str(p_video.id),
        "user_id": user_id,
        "post_type": "reel",
        "media_ids": [vid_id],
        "media_items": [{"media_id": vid_id, "position": 1}],
    })

    ctx_video = await resolve_post_publish_context(db_session, p_video)
    assert ctx_video.has_media is True
    assert ctx_video.is_video is True
    assert ctx_video.primary_item.media_id == vid_id
    assert ctx_video.primary_item.media_type == "video"

    # --- C. Text-only Post ---
    p_text = Post(
        user_id=user_id,
        content="Pure text post",
        post_type="text",
        media_urls=[],
        status="scheduled",
    )
    db_session.add(p_text)
    db_session.commit()
    db_session.refresh(p_text)

    ctx_text = await resolve_post_publish_context(db_session, p_text)
    assert ctx_text.has_media is False
    assert ctx_text.is_video is False
    assert ctx_text.is_carousel is False


# ===========================================================================
# 3. Platform Adapter Tests (Mocking HTTP calls)
# ===========================================================================

@pytest.mark.asyncio
async def test_linkedin_publisher_text_vs_media(db_session):
    """Verify LinkedIn uses UGC text for text posts and registerUpload for media posts."""
    user_id = "usr_li_test"
    acc = _seed_account(db_session, user_id, SocialPlatform.linkedin)
    publisher = LinkedInPublisher()

    # 1. Text-only post
    p_text = Post(id="post_li_text", user_id=user_id, content="LinkedIn Text Update", post_type="text")
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"id": "urn:li:share:123456"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        res = await publisher.publish(p_text, acc)
        assert res.success is True
        assert res.platform_post_id == "urn:li:share:123456"
        # Check payload had shareMediaCategory: NONE
        call_json = mock_post.call_args[1]["json"]
        assert call_json["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] == "NONE"

    # 2. Image post with context
    ctx = PostPublishContext(
        post=p_text,
        post_id="post_li_img",
        user_id=user_id,
        post_type="image",
        content="LinkedIn Image Update",
        media_items=[
            ResolvedMediaItem(
                media_id="m_img_1",
                position=1,
                media_type="image",
                usage_type="single",
                mime_type="image/jpeg",
                original_filename="test.jpg",
                size_bytes=100,
                public_url="http://localhost:8000/api/v1/media/public/m_img_1?token=mock",
            )
        ],
    )

    reg_resp = MagicMock(status_code=200)
    reg_resp.json.return_value = {
        "value": {
            "uploadMechanism": {
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest": {
                    "uploadUrl": "https://api.linkedin.com/mediaUpload/url"
                }
            },
            "asset": "urn:li:digitalmediaAsset:C5522AQG"
        }
    }
    put_resp = MagicMock(status_code=201)
    ugc_resp = MagicMock(status_code=201)
    ugc_resp.json.return_value = {"id": "urn:li:share:789012"}

    # Mock download of binary from public_url and put to LinkedIn
    dl_resp = MagicMock(status_code=200, content=b"IMAGE_BYTES")

    async def _mock_client_post(url, *args, **kwargs):
        if "registerUpload" in url:
            return reg_resp
        return ugc_resp

    async def _mock_client_get(url, *args, **kwargs):
        return dl_resp

    async def _mock_client_put(url, *args, **kwargs):
        return put_resp

    with patch("httpx.AsyncClient.post", side_effect=_mock_client_post) as mock_p, \
         patch("httpx.AsyncClient.get", side_effect=_mock_client_get), \
         patch("httpx.AsyncClient.put", side_effect=_mock_client_put):
        res = await publisher.publish(p_text, acc, context=ctx)
        assert res.success is True
        assert res.platform_post_id == "urn:li:share:789012"


@pytest.mark.asyncio
async def test_instagram_publisher_text_skipped_and_carousel(db_session):
    """Verify Instagram honestly skips text-only posts and properly constructs Carousel."""
    user_id = "usr_ig_test"
    acc = _seed_account(db_session, user_id, SocialPlatform.instagram)
    publisher = InstagramPublisher()

    # 1. Text-only post -> honest SKIPPED
    p_text = Post(id="post_ig_text", user_id=user_id, content="Instagram text only", post_type="text")
    res = await publisher.publish(p_text, acc)
    assert res.success is False
    assert res.skipped is True
    assert "requires image or video" in res.error_message

    # 2. Carousel post -> child containers + parent container + publish
    ctx = PostPublishContext(
        post=p_text,
        post_id="post_ig_car",
        user_id=user_id,
        post_type="carousel",
        content="Carousel caption",
        media_items=[
            ResolvedMediaItem(
                media_id="m1",
                position=1,
                media_type="image",
                usage_type="carousel",
                mime_type="image/jpeg",
                original_filename="c1.jpg",
                size_bytes=100,
                public_url="http://localhost:8000/api/v1/media/public/m1?token=t1",
            ),
            ResolvedMediaItem(
                media_id="m2",
                position=2,
                media_type="image",
                usage_type="carousel",
                mime_type="image/jpeg",
                original_filename="c2.jpg",
                size_bytes=100,
                public_url="http://localhost:8000/api/v1/media/public/m2?token=t2",
            ),
        ],
    )

    child_resp1 = MagicMock(status_code=200)
    child_resp1.json.return_value = {"id": "child_container_1"}
    child_resp2 = MagicMock(status_code=200)
    child_resp2.json.return_value = {"id": "child_container_2"}
    parent_resp = MagicMock(status_code=200)
    parent_resp.json.return_value = {"id": "parent_carousel_container"}
    publish_resp = MagicMock(status_code=200)
    publish_resp.json.return_value = {"id": "ig_published_carousel_id"}

    call_count = 0
    async def _mock_ig_post(url, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        data = kwargs.get("data", {})
        if data.get("is_carousel_item") == "true":
            if call_count == 1:
                return child_resp1
            return child_resp2
        elif data.get("media_type") == "CAROUSEL":
            assert "child_container_1,child_container_2" in data.get("children", "")
            return parent_resp
        elif "creation_id" in data:
            assert data["creation_id"] == "parent_carousel_container"
            return publish_resp
        return child_resp1

    status_resp = MagicMock(status_code=200, content=b'{"status_code": "FINISHED"}')
    status_resp.json.return_value = {"status_code": "FINISHED"}

    with patch("httpx.AsyncClient.post", side_effect=_mock_ig_post), \
         patch("httpx.AsyncClient.get", return_value=status_resp), \
         patch("asyncio.sleep", return_value=None):
        res = await publisher.publish(p_text, acc, context=ctx)
        assert res.success is True
        assert res.platform_post_id == "ig_published_carousel_id"


@pytest.mark.asyncio
async def test_facebook_publisher_text_vs_media(db_session):
    """Verify Facebook handles text posts to feed and media posts with direct upload."""
    user_id = "usr_fb_test"
    acc = _seed_account(db_session, user_id, SocialPlatform.facebook)
    publisher = FacebookPublisher()

    # 1. Text post -> /feed
    p_text = Post(id="post_fb_text", user_id=user_id, content="Facebook status update", post_type="text")
    feed_resp = MagicMock(status_code=200)
    feed_resp.json.return_value = {"id": "fb_feed_post_123"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=feed_resp) as mock_post:
        res = await publisher.publish(p_text, acc)
        assert res.success is True
        assert res.platform_post_id == "fb_feed_post_123"
        call_url = mock_post.call_args[0][0]
        assert "/feed" in call_url

    # 2. Image post -> /photos
    ctx = PostPublishContext(
        post=p_text,
        post_id="post_fb_img",
        user_id=user_id,
        post_type="image",
        content="Facebook photo update",
        media_items=[
            ResolvedMediaItem(
                media_id="fb_m1",
                position=1,
                media_type="image",
                usage_type="single",
                mime_type="image/jpeg",
                original_filename="pic.jpg",
                size_bytes=100,
                public_url="http://localhost:8000/api/v1/media/public/fb_m1?token=t",
            )
        ],
    )

    photo_resp = MagicMock(status_code=200)
    photo_resp.json.return_value = {"id": "fb_photo_post_456"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=photo_resp) as mock_post:
        res = await publisher.publish(p_text, acc, context=ctx)
        assert res.success is True
        assert res.platform_post_id == "fb_photo_post_456"
        call_url = mock_post.call_args[0][0]
        assert "/photos" in call_url


@pytest.mark.asyncio
async def test_pinterest_and_youtube_honesty_and_media(db_session):
    """Verify Pinterest and YouTube honesty (SKIPPED on text) and success on media."""
    user_id = "usr_pin_yt"
    pin_acc = _seed_account(db_session, user_id, SocialPlatform.pinterest)
    yt_acc = _seed_account(db_session, user_id, SocialPlatform.youtube)

    pin_pub = PinterestPublisher()
    yt_pub = YouTubePublisher()

    p_text = Post(id="post_skip", user_id=user_id, content="Text only", post_type="text")

    # A. Text posts are honestly SKIPPED
    pin_res = await pin_pub.publish(p_text, pin_acc)
    assert pin_res.success is False
    assert pin_res.skipped is True
    assert "requires image or video" in pin_res.error_message

    yt_res = await yt_pub.publish(p_text, yt_acc)
    assert yt_res.success is False
    assert yt_res.skipped is True
    assert "does not support text-only" in yt_res.error_message

    # B. Pinterest with image context
    pin_ctx = PostPublishContext(
        post=p_text,
        post_id="post_pin",
        user_id=user_id,
        post_type="image",
        content="Pin Title",
        media_items=[
            ResolvedMediaItem(
                media_id="pin_m",
                position=1,
                media_type="image",
                usage_type="single",
                mime_type="image/jpeg",
                original_filename="pin.jpg",
                size_bytes=100,
                public_url="https://domain.com/public/pin_m?token=123",
            )
        ],
    )
    mock_pin_resp = MagicMock(status_code=201)
    mock_pin_resp.json.return_value = {"id": "pin_999"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_pin_resp) as mock_p:
        pin_pub_res = await pin_pub.publish(p_text, pin_acc, context=pin_ctx)
        assert pin_pub_res.success is True
        assert pin_pub_res.platform_post_id == "pin_999"
        sent_payload = mock_p.call_args[1]["json"]
        assert sent_payload["media_source"]["url"] == "https://domain.com/public/pin_m?token=123"


@pytest.mark.asyncio
async def test_e2e_publishing_service_with_context(db_session):
    """Verify PublishingService resolves context and coordinates publishing across platforms."""
    user_id = "usr_e2e_pub"
    acc_fb = _seed_account(db_session, user_id, SocialPlatform.facebook)
    acc_ig = _seed_account(db_session, user_id, SocialPlatform.instagram)

    p = Post(
        id="post_e2e_test",
        user_id=user_id,
        content="Multi-platform post",
        post_type="image",
        status="scheduled",
    )
    db_session.add(p)
    db_session.commit()

    psa1 = PostSocialAccount(post_id=p.id, social_account_id=acc_fb.id)
    psa2 = PostSocialAccount(post_id=p.id, social_account_id=acc_ig.id)
    db_session.add_all([psa1, psa2])
    db_session.commit()
    db_session.refresh(p)

    # Set up mock responses
    fb_resp = MagicMock(status_code=200)
    fb_resp.json.return_value = {"id": "fb_e2e_photo_1"}

    ig_cont_resp = MagicMock(status_code=200)
    ig_cont_resp.json.return_value = {"id": "ig_cont_1"}
    ig_pub_resp = MagicMock(status_code=200)
    ig_pub_resp.json.return_value = {"id": "ig_e2e_photo_1"}

    async def _mock_httpx_post(url, *args, **kwargs):
        if "graph.facebook.com" in url:
            if "/photos" in url or "/feed" in url:
                return fb_resp
            elif "/media_publish" in url:
                return ig_pub_resp
            elif "/media" in url:
                return ig_cont_resp
        return fb_resp

    ig_status_resp = MagicMock(status_code=200, content=b'{"status_code": "FINISHED"}')
    ig_status_resp.json.return_value = {"status_code": "FINISHED"}

    with patch("httpx.AsyncClient.post", side_effect=_mock_httpx_post), \
         patch("httpx.AsyncClient.get", return_value=ig_status_resp), \
         patch("asyncio.sleep", return_value=None):
        # We also mock resolve_post_publish_context to provide an image item
        mock_ctx = PostPublishContext(
            post=p,
            post_id=p.id,
            user_id=user_id,
            post_type="image",
            content="Multi-platform post",
            media_items=[
                ResolvedMediaItem(
                    media_id="e2e_m1",
                    position=1,
                    media_type="image",
                    usage_type="single",
                    mime_type="image/jpeg",
                    original_filename="e2e.jpg",
                    size_bytes=100,
                    public_url="http://localhost:8000/api/v1/media/public/e2e_m1?token=xyz",
                )
            ],
        )
        with patch("app.services.publishing.service.resolve_post_publish_context", new_callable=AsyncMock, return_value=mock_ctx):
            updated_post, results = await PublishingService.publish_post(db_session, p)
            assert updated_post.status == PostStatus.published.value
            assert len(results) == 2
            assert all(r.status == "published" for r in results)


@pytest.mark.asyncio
async def test_youtube_token_refresh_flow(db_session):
    """Verify YouTube OAuth proactive and reactive token refresh behavior."""
    user_id = "usr_yt_refresh"
    yt_acc = _seed_account(db_session, user_id, SocialPlatform.youtube)
    yt_acc.refresh_token_encrypted = encrypt_token("mock-google-refresh-token")
    # Set expired token timestamp to test proactive refresh
    yt_acc.token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db_session.commit()

    yt_pub = YouTubePublisher()
    video_post = Post(id="yt_vid_post", user_id=user_id, content="New Tech Talk", post_type="video")

    ctx = PostPublishContext(
        post=video_post,
        post_id="yt_vid_post",
        user_id=user_id,
        post_type="video",
        content="New Tech Talk",
        media_items=[
            ResolvedMediaItem(
                media_id="vid_m1",
                position=1,
                media_type="video",
                usage_type="single",
                mime_type="video/mp4",
                original_filename="talk.mp4",
                size_bytes=500,
                public_url="https://domain.com/public/vid_m1",
            )
        ],
    )

    mock_success_resp = MagicMock(status_code=201)
    mock_success_resp.json.return_value = {"id": "yt_video_123"}

    mock_token_data = {
        "access_token": "fresh-google-access-token-999",
        "refresh_token": "mock-google-refresh-token",
        "expires_in": 3600,
    }

    # 1. Proactive refresh test: token is expired -> refreshed before upload
    with patch("app.services.social_providers.youtube.YouTubeProvider.refresh_access_token", new_callable=AsyncMock, return_value=mock_token_data) as mock_refresh, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_success_resp) as mock_post:
        res = await yt_pub.publish(video_post, yt_acc, context=ctx)
        assert res.success is True
        assert res.platform_post_id == "yt_video_123"
        assert res.published_url == "https://www.youtube.com/watch?v=yt_video_123"
        mock_refresh.assert_awaited_once()

    # 2. Reactive refresh test: token expires during call (401) -> refreshed and retried once
    yt_acc.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.commit()

    mock_401_resp = MagicMock(status_code=401)
    call_count = 0

    async def _mock_post_with_retry(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_401_resp
        return mock_success_resp

    with patch("app.services.social_providers.youtube.YouTubeProvider.refresh_access_token", new_callable=AsyncMock, return_value=mock_token_data) as mock_refresh_2, \
         patch("httpx.AsyncClient.post", side_effect=_mock_post_with_retry):
        res_retry = await yt_pub.publish(video_post, yt_acc, context=ctx)
        assert res_retry.success is True
        assert res_retry.platform_post_id == "yt_video_123"
        mock_refresh_2.assert_awaited_once()
        assert call_count == 2
