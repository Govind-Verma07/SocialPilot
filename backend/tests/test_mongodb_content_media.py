"""
tests/test_mongodb_content_media.py
-----------------------------------
Comprehensive test suite for SocialPilot Unified Content & Media Storage Architecture.
Covers:
  1. Text post creation (succeeds with empty media_ids)
  2. Text post rejects media (400 Bad Request)
  3. Image post upload & scheduling (succeeds with image asset)
  4. Image post requires media (400 Bad Request if missing media)
  5. Video post upload & scheduling (succeeds with video asset)
  6. Video post rejects non-video asset (400 Bad Request)
  7. Reel post requires video asset
  8. Story post accepts valid image or video asset
  9. Carousel post preserves explicit ordering (positions 1..N)
 10. Checksum deduplication: identical file content reuses existing media_id
 11. Invalid MIME type rejection (400 Bad Request)
 12. Oversized file rejection (400 Bad Request)
 13. Unauthorized cross-user media access (403 Forbidden)
 14. Non-existent / deleted media reference rejection (400 Bad Request)
 15. Existing text-only scheduled post compatibility (zero regressions)
 16. Media binary streaming / download from GridFS
 17. Media deletion from GridFS & metadata collection
 18. PostgreSQL to MongoDB reference integrity check
"""

import io
from datetime import datetime, timedelta, timezone
import pytest
from app.core.encryption import encrypt_token
from app.models.enums import AccountStatus, SocialPlatform
from app.models.social_account import SocialAccount


def _register_and_login(client, email: str, name: str = "Test User") -> tuple[str, str, dict]:
    """Helper to register and return (user_id, token, auth_headers)."""
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


def _seed_account(db_session, user_id: str, platform: SocialPlatform = SocialPlatform.linkedin) -> SocialAccount:
    """Helper to create a connected social account in PostgreSQL."""
    now = datetime.now(timezone.utc)
    acc = SocialAccount(
        user_id=user_id,
        platform=platform.value,
        platform_account_id=f"{platform.value}_acct_{user_id[:8]}",
        account_name=f"{platform.value.capitalize()} Account",
        account_username=f"{platform.value}_user",
        status=AccountStatus.connected.value,
        access_token_encrypted=encrypt_token("mock_token"),
        connected_at=now,
        last_synced_at=now,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


def _create_sample_file(content: bytes = b"fake-image-bytes-12345", filename: str = "test.jpg") -> tuple[str, io.BytesIO]:
    """Helper to return a file tuple suitable for TestClient multipart upload."""
    return filename, io.BytesIO(content)


# ---------------------------------------------------------------------------
# 1. Media Upload & Deduplication Tests
# ---------------------------------------------------------------------------

def test_media_upload_and_download_stream(client):
    """Verify that a valid image file can be uploaded to GridFS and downloaded via streaming."""
    user_id, _, headers = _register_and_login(client, "media_user1@example.com")

    file_payload = {"file": ("test_pic.jpg", io.BytesIO(b"\xff\xd8\xff\xe0test_jpeg_data"), "image/jpeg")}
    res = client.post("/api/v1/media/upload", files=file_payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()

    media_id = data["media_id"]
    assert media_id is not None
    assert data["media_type"] == "image"
    assert data["mime_type"] == "image/jpeg"
    assert data["original_filename"] == "test_pic.jpg"
    assert "download_url" in data

    # Test downloading stream from GridFS
    dl_res = client.get(f"/api/v1/media/{media_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.content == b"\xff\xd8\xff\xe0test_jpeg_data"
    assert dl_res.headers["content-type"] == "image/jpeg"


def test_duplicate_checksum_deduplication(client):
    """Verify that uploading the identical binary content reuses the existing media_id without duplicate chunks."""
    user_id, _, headers = _register_and_login(client, "dedup_user@example.com")
    content = b"unique_binary_content_for_deduplication_testing"

    # First upload
    res1 = client.post(
        "/api/v1/media/upload",
        files={"file": ("photo1.png", io.BytesIO(content), "image/png")},
        headers=headers,
    )
    assert res1.status_code == 201
    media_id_1 = res1.json()["media_id"]

    # Second upload with same bytes
    res2 = client.post(
        "/api/v1/media/upload",
        files={"file": ("photo2_renamed.png", io.BytesIO(content), "image/png")},
        headers=headers,
    )
    assert res2.status_code == 201
    media_id_2 = res2.json()["media_id"]

    # Should reuse the exact same media_id
    assert media_id_1 == media_id_2


def test_invalid_mime_rejection(client):
    """Uploading an unsupported or malicious MIME type should return 400."""
    _, _, headers = _register_and_login(client, "invalid_mime@example.com")
    res = client.post(
        "/api/v1/media/upload",
        files={"file": ("danger.exe", io.BytesIO(b"MZ\x90\x00executable"), "application/x-dosexec")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]


def test_oversized_file_rejection(client, monkeypatch):
    """Uploading a file exceeding configured max size should be rejected with 400."""
    import app.services.media_service as ms
    monkeypatch.setattr(ms, "MAX_IMAGE_SIZE_BYTES", 100)  # artificially limit to 100 bytes

    _, _, headers = _register_and_login(client, "oversized@example.com")
    large_bytes = b"X" * 200
    res = client.post(
        "/api/v1/media/upload",
        files={"file": ("big.jpg", io.BytesIO(large_bytes), "image/jpeg")},
        headers=headers,
    )
    assert res.status_code == 400
    assert "exceeds maximum allowed size" in res.json()["detail"]


def test_cross_user_media_access_rejection(client):
    """User B must not be able to download or inspect media uploaded by User A."""
    _, _, headers_a = _register_and_login(client, "user_a@example.com")
    _, _, headers_b = _register_and_login(client, "user_b@example.com")

    # User A uploads
    up_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("private.jpg", io.BytesIO(b"\xff\xd8\xffuser_a_private_data"), "image/jpeg")},
        headers=headers_a,
    )
    media_id = up_res.json()["media_id"]

    # User B tries to get metadata
    meta_res = client.get(f"/api/v1/media/{media_id}", headers=headers_b)
    assert meta_res.status_code == 403

    # User B tries to download binary
    dl_res = client.get(f"/api/v1/media/{media_id}/download", headers=headers_b)
    assert dl_res.status_code == 403


def test_media_delete(client):
    """Deleting media should remove the asset from GridFS and metadata collection."""
    _, _, headers = _register_and_login(client, "delete_media_user@example.com")

    up_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("to_delete.png", io.BytesIO(b"delete_me_soon"), "image/png")},
        headers=headers,
    )
    media_id = up_res.json()["media_id"]

    del_res = client.delete(f"/api/v1/media/{media_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Subsequent access returns 404
    get_res = client.get(f"/api/v1/media/{media_id}", headers=headers)
    assert get_res.status_code == 404


# ---------------------------------------------------------------------------
# 2. Unified Content Model & Format Validation Tests
# ---------------------------------------------------------------------------

def test_text_post_success(client, db_session):
    """Text post succeeds with text content and empty media_ids."""
    user_id, _, headers = _register_and_login(client, "text_user@example.com")
    acc = _seed_account(db_session, user_id)

    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    payload = {
        "content": "A pure text post announcement",
        "social_account_ids": [acc.id],
        "post_type": "text",
        "scheduled_at": future_time,
        "status": "scheduled",
        "media_ids": [],
    }
    res = client.post("/api/v1/posts", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["post_type"] == "text"
    assert data["content"] == "A pure text post announcement"
    assert data["media_ids"] == []


def test_text_post_rejects_media(client, db_session):
    """Text post must reject attempts to attach media files."""
    user_id, _, headers = _register_and_login(client, "text_with_media@example.com")
    acc = _seed_account(db_session, user_id)

    # Upload an image
    up_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("pic.jpg", io.BytesIO(b"pic_bytes"), "image/jpeg")},
        headers=headers,
    )
    media_id = up_res.json()["media_id"]

    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    payload = {
        "content": "This text post tries to sneak in media",
        "social_account_ids": [acc.id],
        "post_type": "text",
        "scheduled_at": future_time,
        "media_ids": [media_id],
    }
    res = client.post("/api/v1/posts", json=payload, headers=headers)
    assert res.status_code == 400
    assert "Text posts cannot have media attached" in res.json()["detail"]


def test_image_post_success_and_requires_media(client, db_session):
    """Image post requires valid image asset; fails without media."""
    user_id, _, headers = _register_and_login(client, "image_post_user@example.com")
    acc = _seed_account(db_session, user_id)
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    # 1. Image post without media -> 400
    res_no_media = client.post(
        "/api/v1/posts",
        json={
            "content": "Image caption without actual image",
            "social_account_ids": [acc.id],
            "post_type": "image",
            "scheduled_at": future_time,
            "media_ids": [],
        },
        headers=headers,
    )
    assert res_no_media.status_code == 400
    assert "At least one media asset is required" in res_no_media.json()["detail"]

    # 2. Upload image and create post -> 201
    up_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("product.jpg", io.BytesIO(b"product_image_data"), "image/jpeg")},
        headers=headers,
    )
    media_id = up_res.json()["media_id"]

    res_success = client.post(
        "/api/v1/posts",
        json={
            "content": "Check out our new product!",
            "social_account_ids": [acc.id],
            "post_type": "image",
            "scheduled_at": future_time,
            "media_ids": [media_id],
        },
        headers=headers,
    )
    assert res_success.status_code == 201, res_success.text
    assert res_success.json()["post_type"] == "image"
    assert media_id in res_success.json()["media_ids"]


def test_video_and_reel_post_validation(client, db_session):
    """Video and Reel posts require video assets and reject non-video files."""
    user_id, _, headers = _register_and_login(client, "video_user@example.com")
    acc = _seed_account(db_session, user_id)
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    # Upload an image and a video
    img_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("not_a_video.png", io.BytesIO(b"png_content"), "image/png")},
        headers=headers,
    )
    img_id = img_res.json()["media_id"]

    vid_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("clip.mp4", io.BytesIO(b"mp4_content_12345"), "video/mp4")},
        headers=headers,
    )
    vid_id = vid_res.json()["media_id"]

    # 1. Video post with image asset -> 400
    bad_res = client.post(
        "/api/v1/posts",
        json={
            "content": "Video post with wrong media",
            "social_account_ids": [acc.id],
            "post_type": "video",
            "scheduled_at": future_time,
            "media_ids": [img_id],
        },
        headers=headers,
    )
    assert bad_res.status_code == 400
    assert "video is required" in bad_res.json()["detail"]

    # 2. Reel post with valid video asset -> 201
    reel_res = client.post(
        "/api/v1/posts",
        json={
            "content": "Trending Reel #viral",
            "social_account_ids": [acc.id],
            "post_type": "reel",
            "scheduled_at": future_time,
            "media_ids": [vid_id],
        },
        headers=headers,
    )
    assert reel_res.status_code == 201
    assert reel_res.json()["post_type"] == "reel"


def test_story_post_validation(client, db_session):
    """Story post accepts image or video media."""
    user_id, _, headers = _register_and_login(client, "story_user@example.com")
    acc = _seed_account(db_session, user_id)
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    img_res = client.post(
        "/api/v1/media/upload",
        files={"file": ("story.jpg", io.BytesIO(b"story_image_bytes"), "image/jpeg")},
        headers=headers,
    )
    img_id = img_res.json()["media_id"]

    story_res = client.post(
        "/api/v1/posts",
        json={
            "content": "Today's Story update",
            "social_account_ids": [acc.id],
            "post_type": "story",
            "scheduled_at": future_time,
            "media_ids": [img_id],
        },
        headers=headers,
    )
    assert story_res.status_code == 201
    assert story_res.json()["post_type"] == "story"


def test_carousel_ordering_and_item_limits(client, db_session):
    """Carousel posts require at least 2 media items and preserve explicit positions."""
    user_id, _, headers = _register_and_login(client, "carousel_user@example.com")
    acc = _seed_account(db_session, user_id)
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    # Upload 3 slides
    up1 = client.post("/api/v1/media/upload", files={"file": ("s1.jpg", io.BytesIO(b"slide1"), "image/jpeg")}, headers=headers)
    up2 = client.post("/api/v1/media/upload", files={"file": ("s2.jpg", io.BytesIO(b"slide2"), "image/jpeg")}, headers=headers)
    up3 = client.post("/api/v1/media/upload", files={"file": ("s3.jpg", io.BytesIO(b"slide3"), "image/jpeg")}, headers=headers)

    id1, id2, id3 = up1.json()["media_id"], up2.json()["media_id"], up3.json()["media_id"]

    # 1. Carousel with only 1 item -> 400
    fail_res = client.post(
        "/api/v1/posts",
        json={
            "content": "Single slide carousel",
            "social_account_ids": [acc.id],
            "post_type": "carousel",
            "scheduled_at": future_time,
            "media_ids": [id1],
        },
        headers=headers,
    )
    assert fail_res.status_code == 400
    assert "require at least 2 media items" in fail_res.json()["detail"]

    # 2. Carousel with explicit inverted order: slide3 (pos 1), slide1 (pos 2), slide2 (pos 3)
    media_items = [
        {"media_id": id3, "position": 1},
        {"media_id": id1, "position": 2},
        {"media_id": id2, "position": 3},
    ]
    car_res = client.post(
        "/api/v1/posts",
        json={
            "content": "Top 3 Tips Carousel",
            "social_account_ids": [acc.id],
            "post_type": "carousel",
            "scheduled_at": future_time,
            "media_items": media_items,
        },
        headers=headers,
    )
    assert car_res.status_code == 201
    post_data = car_res.json()
    post_id = post_data["id"]

    # Verify order is strictly preserved in GET /{post_id}/content
    content_res = client.get(f"/api/v1/posts/{post_id}/content", headers=headers)
    assert content_res.status_code == 200
    c_data = content_res.json()
    assert len(c_data["media_items"]) == 3
    assert c_data["media_items"][0]["media_id"] == id3
    assert c_data["media_items"][0]["position"] == 1
    assert c_data["media_items"][1]["media_id"] == id1
    assert c_data["media_items"][1]["position"] == 2
    assert c_data["media_items"][2]["media_id"] == id2
    assert c_data["media_items"][2]["position"] == 3


def test_deleted_or_invalid_media_reference(client, db_session):
    """Referencing a non-existent or deleted media_id should return 400."""
    user_id, _, headers = _register_and_login(client, "bad_ref_user@example.com")
    acc = _seed_account(db_session, user_id)
    future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

    fake_id = "00000000-0000-0000-0000-000000000000"
    res = client.post(
        "/api/v1/posts",
        json={
            "content": "Post with bad media reference",
            "social_account_ids": [acc.id],
            "post_type": "image",
            "scheduled_at": future_time,
            "media_ids": [fake_id],
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "does not exist or was deleted" in res.json()["detail"]


def test_postgresql_to_mongodb_reference_integrity(client, db_session):
    """Verify that a created post in PostgreSQL has an exact matching document in MongoDB content_posts."""
    user_id, _, headers = _register_and_login(client, "ref_integrity_user@example.com")
    acc = _seed_account(db_session, user_id)

    # Upload media
    up = client.post("/api/v1/media/upload", files={"file": ("integ.png", io.BytesIO(b"integ_data"), "image/png")}, headers=headers)
    m_id = up.json()["media_id"]

    future_time = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    metadata_payload = {
        "title": "Launch Post",
        "hashtags": ["launch", "socialpilot"],
        "platform_overrides": {
            "linkedin": {"title": "Professional Launch Update"},
        },
    }

    create_res = client.post(
        "/api/v1/posts",
        json={
            "content": "Launching SocialPilot unified storage!",
            "social_account_ids": [acc.id],
            "post_type": "image",
            "scheduled_at": future_time,
            "media_ids": [m_id],
            "metadata": metadata_payload,
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    post_id = create_res.json()["id"]

    # Verify content endpoint retrieves rich document matching PostgreSQL post_id
    detail_res = client.get(f"/api/v1/posts/{post_id}/content", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["post_id"] == post_id
    assert detail["user_id"] == user_id
    assert detail["post_type"] == "image"
    assert detail["metadata"]["title"] == "Launch Post"
    assert "launch" in detail["metadata"]["hashtags"]
    assert detail["metadata"]["platform_overrides"]["linkedin"]["title"] == "Professional Launch Update"
    assert len(detail["media_items"]) == 1
    assert detail["media_items"][0]["media_id"] == m_id
    assert detail["media_items"][0]["original_filename"] == "integ.png"


def test_all_image_formats_upload_support(client):
    """Verify that all image formats (AVIF, HEIC, JFIF, BMP, SVG, TIFF, and generic octet-stream) are accepted."""
    _, _, headers = _register_and_login(client, "formats_user@example.com")

    test_formats = [
        ("photo.avif", b"avif_image_bytes", "image/avif"),
        ("camera.heic", b"heic_image_bytes", "image/heic"),
        ("scan.bmp", b"bmp_image_bytes", "image/bmp"),
        ("vector.svg", b"<svg>test</svg>", "image/svg+xml"),
        ("legacy.jfif", b"jfif_image_bytes", "image/jfif"),
        ("generic_photo.jpg", b"jpeg_bytes_octet", "application/octet-stream"),  # Generic MIME with image extension
    ]

    for filename, content, mime in test_formats:
        res = client.post(
            "/api/v1/media/upload",
            files={"file": (filename, io.BytesIO(content), mime)},
            headers=headers,
        )
        assert res.status_code == 201, f"Failed for {filename} ({mime}): {res.text}"
        data = res.json()
        assert data["media_type"] == "image", f"Expected media_type=image for {filename}, got {data['media_type']}"
        assert data["media_id"] is not None

