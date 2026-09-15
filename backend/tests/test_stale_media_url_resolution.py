"""
tests/test_stale_media_url_resolution.py
----------------------------------------
Unit tests verifying:
1. Public media base URL priority:
   PUBLIC_BASE_URL -> BACKEND_PUBLIC_URL -> PUBLIC_MEDIA_BASE_URL -> PINGGY_URL/PINGGY_BASE_URL -> RENDER_EXTERNAL_URL
2. Never generating localhost or 127.0.0.1 for external platforms.
3. Dynamic publish-time URL resolution prevents stale Pinggy hostnames in post.media_urls from leaking to Instagram.
4. Pinggy development mode reports clear tunnel expired error when probe fails.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock
from app.core.config import Settings
from app.services.publishing.adapters.instagram import InstagramPublisher
from app.services.publishing.media_resolver import PostPublishContext, ResolvedMediaItem
from app.models.post import Post
from app.models.social_account import SocialAccount


def test_public_base_url_priority():
    """Verify exact priority of public base URL resolution."""
    # Priority 1: PUBLIC_BASE_URL
    s1 = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="secret",
        PUBLIC_BASE_URL="https://p1.example.com",
        BACKEND_PUBLIC_URL="https://p2.example.com",
        PUBLIC_MEDIA_BASE_URL="https://p3.example.com",
        PINGGY_URL="https://p4.example.com",
        PINGGY_BASE_URL="https://p5.example.com",
        RENDER_EXTERNAL_URL="https://p6.example.com",
    )
    assert s1.effective_public_media_base_url == "https://p1.example.com"

    # Priority 2: BACKEND_PUBLIC_URL
    s2 = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="secret",
        PUBLIC_BASE_URL="",
        BACKEND_PUBLIC_URL="https://p2.example.com",
        PUBLIC_MEDIA_BASE_URL="https://p3.example.com",
    )
    assert s2.effective_public_media_base_url == "https://p2.example.com"

    # Priority 3: PUBLIC_MEDIA_BASE_URL
    s3 = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="secret",
        PUBLIC_BASE_URL="",
        BACKEND_PUBLIC_URL="",
        PUBLIC_MEDIA_BASE_URL="https://p3.example.com",
        PINGGY_URL="https://p4.example.com",
    )
    assert s3.effective_public_media_base_url == "https://p3.example.com"

    # Priority 4: PINGGY_URL / PINGGY_BASE_URL
    s4 = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="secret",
        PUBLIC_BASE_URL="",
        BACKEND_PUBLIC_URL="",
        PUBLIC_MEDIA_BASE_URL="",
        PINGGY_BASE_URL="https://p5.run.pinggy-free.link",
        RENDER_EXTERNAL_URL="https://p6.onrender.com",
    )
    assert s4.effective_public_media_base_url == "https://p5.run.pinggy-free.link"

    # Priority 5: RENDER_EXTERNAL_URL
    s5 = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="secret",
        PUBLIC_BASE_URL="",
        BACKEND_PUBLIC_URL="",
        PUBLIC_MEDIA_BASE_URL="",
        PINGGY_URL="",
        PINGGY_BASE_URL="",
        RENDER_EXTERNAL_URL="https://myapp.onrender.com",
    )
    assert s5.effective_public_media_base_url == "https://myapp.onrender.com"


def test_reject_localhost_in_effective_public_media_base_url():
    """Verify that localhost and 127.0.0.1 candidates are ignored for external platforms."""
    s = Settings(
        _env_file=None,
        DATABASE_URL="postgresql://user:pass@localhost:5432/db",
        JWT_SECRET_KEY="secret",
        APP_ENV="production",
        PUBLIC_BASE_URL="http://localhost:8000",
        BACKEND_PUBLIC_URL="http://127.0.0.1:8000",
        PUBLIC_MEDIA_BASE_URL="https://valid-render-domain.onrender.com",
    )
    # Even though PUBLIC_BASE_URL is localhost, it skips to the valid external domain
    assert s.effective_public_media_base_url == "https://valid-render-domain.onrender.com"


@pytest.mark.asyncio
async def test_instagram_rewrites_stale_tunnel_url_dynamically():
    """Verify that InstagramPublisher dynamically resolves media_id with current PUBLIC_BASE_URL."""
    from app.core.config import settings

    old_stale_url = "https://old-expired-tunnel.run.pinggy-free.link/api/v1/media/public/test-media-123?token=oldtoken"
    current_live_tunnel = "https://fresh-new-tunnel.run.pinggy-free.link"

    with patch.object(settings, "PUBLIC_BASE_URL", current_live_tunnel), \
         patch.object(settings, "BACKEND_PUBLIC_URL", current_live_tunnel):
        
        post = MagicMock(spec=Post)
        post.id = 999
        post.content = "Test caption"
        post.post_type = "image"
        post.media_urls = [old_stale_url]

        account = MagicMock(spec=SocialAccount)
        account.access_token = "mock-enc-token"

        context = PostPublishContext(
            post=post,
            post_id="999",
            user_id="user_1",
            post_type="image",
            content="Test caption",
            media_items=[
                ResolvedMediaItem(
                    media_id="test-media-123",
                    position=1,
                    media_type="image",
                    usage_type="single",
                    mime_type="image/jpeg",
                    original_filename="test.jpg",
                    size_bytes=1000,
                    public_url=old_stale_url,
                )
            ],
        )

        publisher = InstagramPublisher()

        # Mock decrypt_token, httpx probe, and Graph API container creation
        with patch("app.services.publishing.adapters.instagram.decrypt_token", return_value="IGAA_mock_token"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            
            # Reachability probe returns 200 image/jpeg
            probe_resp = MagicMock(status_code=200, headers={"content-type": "image/jpeg"})
            # Container creation returns 200 {"id": "container_123"}
            container_resp = MagicMock(status_code=200, content=b'{"id": "container_123"}')
            container_resp.json.return_value = {"id": "container_123"}
            # Publish returns 200 {"id": "post_123"}
            pub_resp = MagicMock(status_code=200, content=b'{"id": "post_123"}')
            pub_resp.json.return_value = {"id": "post_123"}

            mock_client.get.return_value = probe_resp
            mock_client.post.side_effect = [container_resp, pub_resp]

            # Temporarily unmark test to test full pipeline logic
            with patch("sys.modules", {"pytest": None}):
                res = await publisher.publish(post, account, context=context)

            # Check that container POST received image_url using the NEW live tunnel, NOT the old stale tunnel!
            container_call = mock_client.post.call_args_list[0]
            called_data = container_call.kwargs.get("data") or {}
            used_image_url = called_data.get("image_url")

            assert used_image_url is not None
            assert current_live_tunnel in used_image_url
            assert "old-expired-tunnel" not in used_image_url
            assert "test-media-123" in used_image_url


@pytest.mark.asyncio
async def test_pinggy_expired_probe_returns_clear_error():
    """Verify that when Pinggy tunnel fails DNS or connect, clear error is returned."""
    import httpx
    from app.core.config import settings

    stale_pinggy_url = "https://expired-pinggy.run.pinggy-free.link"

    with patch.object(settings, "PUBLIC_BASE_URL", stale_pinggy_url), \
         patch.object(settings, "BACKEND_PUBLIC_URL", stale_pinggy_url):
        
        post = MagicMock(spec=Post)
        post.id = 101
        post.content = "Caption"
        post.post_type = "image"
        post.media_urls = [f"{stale_pinggy_url}/api/v1/media/public/m1?token=tok"]

        account = MagicMock(spec=SocialAccount)
        account.access_token = "mock"

        context = PostPublishContext(
            post=post,
            post_id="101",
            user_id="user_1",
            post_type="image",
            content="Caption",
            media_items=[
                ResolvedMediaItem(
                    media_id="m1",
                    position=1,
                    media_type="image",
                    usage_type="single",
                    mime_type="image/jpeg",
                    original_filename="a.jpg",
                    size_bytes=100,
                    public_url=f"{stale_pinggy_url}/api/v1/media/public/m1?token=tok",
                )
            ],
        )

        publisher = InstagramPublisher()

        with patch("app.services.publishing.adapters.instagram.decrypt_token", return_value="IGAA_tok"), \
             patch("httpx.AsyncClient") as mock_client_cls:
            
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            # Simulate DNS failure on expired Pinggy
            mock_client.get.side_effect = httpx.ConnectError("[Errno 11001] getaddrinfo failed")

            modules_without_pytest = {k: v for k, v in sys.modules.items() if k != "pytest"}
            with patch.dict(sys.modules, modules_without_pytest, clear=True):
                res = await publisher.publish(post, account, context=context)

            assert res.success is False
            assert "Pinggy tunnel is unavailable/expired. Restart the tunnel and update PUBLIC_BASE_URL." in res.error_message


@pytest.mark.asyncio
async def test_instagram_media_publish_called_only_after_finished():
    """Verify that media_publish is called ONLY after container status_code becomes FINISHED."""
    live_tunnel = "https://fresh-tunnel.run.pinggy-free.link"
    publisher = InstagramPublisher()

    post = MagicMock(spec=Post)
    post.id = 201
    post.content = "Test ready post"
    post.post_type = "image"
    post.media_urls = [f"{live_tunnel}/api/v1/media/public/media-ok?token=tok"]

    account = MagicMock(spec=SocialAccount)
    account.access_token_encrypted = "enc_token"

    context = PostPublishContext(
        post=post,
        post_id="201",
        user_id="user_test",
        post_type="image",
        content="Test ready post",
        media_items=[
            ResolvedMediaItem(
                media_id="media-ok",
                position=1,
                media_type="image",
                usage_type="single",
                mime_type="image/jpeg",
                original_filename="ok.jpg",
                size_bytes=500,
                public_url=f"{live_tunnel}/api/v1/media/public/media-ok?token=tok",
            )
        ],
    )

    probe_resp = MagicMock(status_code=200, headers={"content-type": "image/jpeg"})
    in_progress_resp = MagicMock(status_code=200, content=b'{"status_code": "IN_PROGRESS"}')
    in_progress_resp.json.return_value = {"status_code": "IN_PROGRESS"}
    finished_resp = MagicMock(status_code=200, content=b'{"status_code": "FINISHED"}')
    finished_resp.json.return_value = {"status_code": "FINISHED"}

    container_create_resp = MagicMock(status_code=200, content=b'{"id": "cont_ready_1"}')
    container_create_resp.json.return_value = {"id": "cont_ready_1"}
    publish_resp = MagicMock(status_code=200, content=b'{"id": "ig_post_published_999"}')
    publish_resp.json.return_value = {"id": "ig_post_published_999"}

    post_calls = []
    async def _mock_post(url, *args, **kwargs):
        post_calls.append((url, kwargs.get("data", {})))
        if "/media_publish" in url:
            return publish_resp
        return container_create_resp

    get_calls = []
    async def _mock_get(url, *args, **kwargs):
        get_calls.append((url, kwargs.get("params", {})))
        if "media/public" in url:
            return probe_resp
        # Status check
        if len([c for c in get_calls if "media/public" not in c[0]]) == 1:
            return in_progress_resp
        return finished_resp

    with patch("app.services.publishing.adapters.instagram.decrypt_token", return_value="IGAA_test_tok"), \
         patch("httpx.AsyncClient.post", side_effect=_mock_post), \
         patch("httpx.AsyncClient.get", side_effect=_mock_get), \
         patch("asyncio.sleep", return_value=None):

        res = await publisher.publish(post, account, context=context)

    assert res.success is True
    assert res.platform_post_id == "ig_post_published_999"

    # Verify media_publish was called with creation_id=cont_ready_1
    pub_calls = [c for c in post_calls if "/media_publish" in c[0]]
    assert len(pub_calls) == 1
    assert pub_calls[0][1]["creation_id"] == "cont_ready_1"

    # Verify status was polled twice before publish
    status_probes = [c for c in get_calls if "cont_ready_1" in c[0]]
    assert len(status_probes) == 2
    assert status_probes[0][1].get("fields") == "status_code"


@pytest.mark.asyncio
async def test_instagram_media_container_error_fails_without_publish():
    """Verify that when container returns status_code=ERROR, publish is aborted."""
    live_tunnel = "https://fresh-tunnel.run.pinggy-free.link"
    publisher = InstagramPublisher()

    post = MagicMock(spec=Post)
    post.id = 202
    post.content = "Test err post"
    post.post_type = "image"
    post.media_urls = [f"{live_tunnel}/api/v1/media/public/media-err?token=tok"]

    account = MagicMock(spec=SocialAccount)
    account.access_token_encrypted = "enc_token"

    context = PostPublishContext(
        post=post,
        post_id="202",
        user_id="user_test",
        post_type="image",
        content="Test err post",
        media_items=[
            ResolvedMediaItem(
                media_id="media-err",
                position=1,
                media_type="image",
                usage_type="single",
                mime_type="image/jpeg",
                original_filename="err.jpg",
                size_bytes=500,
                public_url=f"{live_tunnel}/api/v1/media/public/media-err?token=tok",
            )
        ],
    )

    probe_resp = MagicMock(status_code=200, headers={"content-type": "image/jpeg"})
    error_resp = MagicMock(status_code=200, content=b'{"status_code": "ERROR", "status": "Failed to decode image"}')
    error_resp.json.return_value = {"status_code": "ERROR", "status": "Failed to decode image"}

    container_create_resp = MagicMock(status_code=200, content=b'{"id": "cont_err_1"}')
    container_create_resp.json.return_value = {"id": "cont_err_1"}

    post_calls = []
    async def _mock_post(url, *args, **kwargs):
        post_calls.append(url)
        return container_create_resp

    async def _mock_get(url, *args, **kwargs):
        if "media/public" in url:
            return probe_resp
        return error_resp

    with patch("app.services.publishing.adapters.instagram.decrypt_token", return_value="IGAA_test_tok"), \
         patch("httpx.AsyncClient.post", side_effect=_mock_post), \
         patch("httpx.AsyncClient.get", side_effect=_mock_get), \
         patch("asyncio.sleep", return_value=None):

        res = await publisher.publish(post, account, context=context)

    assert res.success is False
    assert "processing error" in res.error_message
    # media_publish was NEVER called
    assert not any("/media_publish" in url for url in post_calls)


@pytest.mark.asyncio
async def test_instagram_media_container_timeout_fails_without_publish():
    """Verify that when container never reaches FINISHED within 10 attempts, it fails with timeout."""
    live_tunnel = "https://fresh-tunnel.run.pinggy-free.link"
    publisher = InstagramPublisher()

    post = MagicMock(spec=Post)
    post.id = 203
    post.content = "Test timeout post"
    post.post_type = "image"
    post.media_urls = [f"{live_tunnel}/api/v1/media/public/media-time?token=tok"]

    account = MagicMock(spec=SocialAccount)
    account.access_token_encrypted = "enc_token"

    context = PostPublishContext(
        post=post,
        post_id="203",
        user_id="user_test",
        post_type="image",
        content="Test timeout post",
        media_items=[
            ResolvedMediaItem(
                media_id="media-time",
                position=1,
                media_type="image",
                usage_type="single",
                mime_type="image/jpeg",
                original_filename="time.jpg",
                size_bytes=500,
                public_url=f"{live_tunnel}/api/v1/media/public/media-time?token=tok",
            )
        ],
    )

    probe_resp = MagicMock(status_code=200, headers={"content-type": "image/jpeg"})
    in_prog_resp = MagicMock(status_code=200, content=b'{"status_code": "IN_PROGRESS"}')
    in_prog_resp.json.return_value = {"status_code": "IN_PROGRESS"}

    container_create_resp = MagicMock(status_code=200, content=b'{"id": "cont_timeout_1"}')
    container_create_resp.json.return_value = {"id": "cont_timeout_1"}

    post_calls = []
    async def _mock_post(url, *args, **kwargs):
        post_calls.append(url)
        return container_create_resp

    poll_count = 0
    async def _mock_get(url, *args, **kwargs):
        nonlocal poll_count
        if "media/public" in url:
            return probe_resp
        poll_count += 1
        return in_prog_resp

    with patch("app.services.publishing.adapters.instagram.decrypt_token", return_value="IGAA_test_tok"), \
         patch("httpx.AsyncClient.post", side_effect=_mock_post), \
         patch("httpx.AsyncClient.get", side_effect=_mock_get), \
         patch("asyncio.sleep", return_value=None):

        res = await publisher.publish(post, account, context=context)

    assert res.success is False
    assert "was not ready within 20 seconds" in res.error_message
    assert poll_count == 10
    # media_publish was NEVER called
    assert not any("/media_publish" in url for url in post_calls)

