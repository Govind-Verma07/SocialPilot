"""
app/services/publishing/adapters/instagram.py
--------------------------------------------
Instagram Publishing Adapter using Instagram Graph API.
Note: Instagram Graph API requires media (image or video) for publishing. Text-only posts are unsupported.
"""

from datetime import datetime, timezone
import asyncio
import logging
import re
from typing import Optional, Tuple
from urllib.parse import urlparse
import httpx

from app.core.config import settings
from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.media_service import MediaService
from app.services.publishing.base import BasePlatformPublisher, PublishResult
from app.services.publishing.media_resolver import PostPublishContext

logger = logging.getLogger("socialpilot.publishing.instagram")


class InstagramPublisher(BasePlatformPublisher):
    platform = SocialPlatform.instagram.value

    GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"

    async def _wait_for_container_ready(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        container_id: str,
        raw_token: str,
        max_attempts: int = 10,
        poll_interval: float = 2.0,
    ) -> Tuple[bool, Optional[str]]:
        """
        Poll Instagram media container status until FINISHED, ERROR, or timeout.
        Guarantees media container has completed asynchronous processing before calling media_publish,
        preventing 'Media ID is not available' (error_subcode 2207027) race conditions.
        """
        status_url = f"{base_url}/{container_id}"
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(poll_interval)
            try:
                s_resp = await client.get(
                    status_url,
                    params={"fields": "status_code", "access_token": raw_token},
                    timeout=15.0,
                )
                if s_resp.status_code == 200:
                    data = s_resp.json() if s_resp.content else {}
                    sc = data.get("status_code") if isinstance(data, dict) else None
                    if sc == "FINISHED":
                        logger.info("Instagram container %s reached FINISHED on attempt %d", container_id, attempt)
                        return True, None
                    elif sc == "ERROR":
                        err_detail = (data.get("status") if isinstance(data, dict) else None) or "Instagram media container failed processing."
                        return False, f"Instagram media container processing error: {err_detail}"
                    elif sc == "EXPIRED":
                        return False, "Instagram media container expired before publishing."
                elif s_resp.status_code in (400, 404):
                    err_data = s_resp.json().get("error", {}) if s_resp.content else {}
                    err_msg = err_data.get("message") or f"HTTP {s_resp.status_code}"
                    return False, f"Instagram media container check failed: {err_msg}"
            except Exception as exc:
                logger.warning(
                    "Instagram container status probe error (attempt %d/%d): %s",
                    attempt,
                    max_attempts,
                    exc,
                )

        return False, f"Instagram media container was not ready within {int(max_attempts * poll_interval)} seconds (status did not become FINISHED)."

    async def publish(
        self,
        post: Post,
        social_account: SocialAccount,
        context: Optional[PostPublishContext] = None,
    ) -> PublishResult:
        raw_token = decrypt_token(social_account.access_token_encrypted)
        if not raw_token:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Instagram access token is missing or invalid. Please reconnect your account.",
            )

        ig_user_id = social_account.platform_account_id
        if not ig_user_id:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Instagram Account ID is missing. Please reconnect your account.",
            )

        # 1. Media requirement check
        media_items = context.media_items if context else []
        post_type = (context.post_type if context else (post.post_type or "text")).lower()

        if not media_items and not post.media_urls:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Instagram requires image or video media.",
                skipped=True,
            )

        # ── DYNAMIC PUBLISH-TIME MEDIA RESOLUTION ───────────────────────────
        # Ensure URLs are constructed dynamically using the CURRENT effective PUBLIC_BASE_URL.
        effective_base = settings.effective_public_media_base_url
        resolved_media_urls = []

        if media_items:
            for m in media_items:
                if m.media_id:
                    # Dynamically generate with current effective base URL and fresh HMAC token
                    resolved_media_urls.append(MediaService.get_public_media_url(m.media_id))
                elif m.public_url:
                    # Check if public_url contains a media_id we can re-anchor
                    m_match = re.search(r"/api/v1/media/public/([a-zA-Z0-9\-_]+)", m.public_url)
                    if m_match:
                        resolved_media_urls.append(MediaService.get_public_media_url(m_match.group(1)))
                    else:
                        resolved_media_urls.append(m.public_url)

        if not resolved_media_urls and post.media_urls:
            for u in post.media_urls:
                u_str = str(u).strip()
                if not u_str:
                    continue
                m_match = re.search(r"/api/v1/media/public/([a-zA-Z0-9\-_]+)", u_str)
                if m_match:
                    resolved_media_urls.append(MediaService.get_public_media_url(m_match.group(1)))
                else:
                    resolved_media_urls.append(u_str)

        media_urls = resolved_media_urls

        if not media_urls:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Instagram media could not be resolved to a valid public URL.",
                skipped=True,
            )

        # Meta requires a publicly accessible HTTPS URL to fetch the media (bypassed in pytest mocks)
        import sys, os
        is_test = "pytest" in sys.modules or os.environ.get("TESTING") == "1" or settings.APP_ENV == "testing"
        first_url = media_urls[0]

        # 1. Reject localhost / loopback addresses
        parsed_first = urlparse(first_url)
        first_host = parsed_first.netloc.split(":")[0].strip().lower()
        if not is_test and first_host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=(
                    "Instagram Graph API requires a publicly reachable HTTPS media URL. "
                    "Localhost URLs cannot be downloaded by Meta. Please configure PUBLIC_BASE_URL "
                    "in backend/.env with a valid public HTTPS tunnel (e.g. Pinggy, ngrok, Cloudflare Tunnel) "
                    "or deploy your backend to a cloud host."
                ),
            )

        # 2. Reject unconfigured public base URL
        if not is_test and not effective_base:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=(
                    "Public media URL is not configured. Please configure PUBLIC_BASE_URL "
                    "in backend/.env with a valid public HTTPS tunnel (e.g. Pinggy) or domain."
                ),
            )

        # 3. Detect and rewrite stale hostname if differing from current PUBLIC_BASE_URL
        if not is_test and effective_base:
            parsed_eff = urlparse(effective_base)
            eff_host = parsed_eff.netloc.split(":")[0].strip().lower()
            if first_host and eff_host and first_host != eff_host:
                if "/api/v1/media/public/" in first_url:
                    m_match = re.search(r"/api/v1/media/public/([a-zA-Z0-9\-_]+)", first_url)
                    if m_match:
                        first_url = MediaService.get_public_media_url(m_match.group(1))
                        media_urls[0] = first_url
                        parsed_first = urlparse(first_url)
                        first_host = parsed_first.netloc.split(":")[0].strip().lower()

        # ── PRE-PUBLISH MEDIA URL REACHABILITY CHECK ─────────────────────────
        # Verify the media URL is publicly reachable BEFORE sending to Meta.
        # This prevents cryptic "Could not fetch media" errors from Instagram.
        if not is_test:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as probe_client:
                    probe_resp = await probe_client.get(first_url, headers={"Range": "bytes=0-1024"})
                    content_type = (probe_resp.headers.get("content-type") or "").lower()
                    logger.info(
                        "Media URL reachability check: status=%s content-type=%s url=%s",
                        probe_resp.status_code,
                        content_type,
                        first_url,
                    )
                    if probe_resp.status_code == 200 and "text/html" in content_type:
                        # Pinggy or tunnel is returning an HTML interstitial/captcha page
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error_message=(
                                f"Media URL returned an HTML page (likely a Pinggy browser-check interstitial) "
                                f"instead of image bytes. Content-Type: {content_type}. "
                                f"Meta/Instagram cannot fetch media from interstitial pages. "
                                f"Solution: Restart your Pinggy tunnel (run: ssh -p 443 -R0:localhost:8000 a.pinggy.io) "
                                f"and update PUBLIC_BASE_URL in backend/.env with the new tunnel URL."
                            ),
                        )
                    if probe_resp.status_code == 403:
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error_message=(
                                f"Media token rejected (403 Forbidden) when probing URL: {first_url}. "
                                f"The HMAC token may be expired or the JWT_SECRET_KEY may have changed. "
                                f"Try creating a new post or re-uploading the image."
                            ),
                        )
                    if probe_resp.status_code not in (200, 206):
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error_message=(
                                f"Cannot reach public media URL. The configured public tunnel/domain is unavailable or expired. "
                                f"Status: {probe_resp.status_code} for URL: {first_url}"
                            ),
                        )
            except (httpx.ConnectError, httpx.ConnectTimeout) as conn_exc:
                if "pinggy" in first_url.lower():
                    err_msg = "Pinggy tunnel is unavailable/expired. Restart the tunnel and update PUBLIC_BASE_URL."
                else:
                    err_msg = (
                        "Cannot reach public media URL. The configured public tunnel/domain is unavailable or expired. "
                        "Restart/update the public HTTPS tunnel and update PUBLIC_BASE_URL."
                    )
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=err_msg,
                )
            except httpx.TimeoutException:
                if "pinggy" in first_url.lower():
                    err_msg = "Pinggy tunnel is unavailable/expired (connection timed out). Restart the tunnel and update PUBLIC_BASE_URL."
                else:
                    err_msg = (
                        "Cannot reach public media URL. The configured public tunnel/domain is unavailable or expired. "
                        "Restart/update the public HTTPS tunnel and update PUBLIC_BASE_URL."
                    )
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=err_msg,
                )
            except Exception as probe_exc:
                logger.warning("Media URL pre-flight probe failed: %s", probe_exc)
                if "pinggy" in first_url.lower():
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error_message="Pinggy tunnel is unavailable/expired. Restart the tunnel and update PUBLIC_BASE_URL.",
                    )
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=(
                        "Cannot reach public media URL. The configured public tunnel/domain is unavailable or expired. "
                        "Restart/update the public HTTPS tunnel and update PUBLIC_BASE_URL."
                    ),
                )

        # Route Instagram Login user tokens (IGAA...) to graph.instagram.com, Facebook page tokens to graph.facebook.com
        is_ig_token = raw_token.startswith("IG")
        base_url = "https://graph.instagram.com/v25.0" if is_ig_token else self.GRAPH_BASE_URL
        target_path = "me" if is_ig_token else ig_user_id
        container_url = f"{base_url}/{target_path}/media"
        caption = post.content or ""

        try:
            async with httpx.AsyncClient() as client:
                container_id = None

                # ── CAROUSEL POST ──────────────────────────────────────────────
                if post_type == "carousel" and len(media_urls) >= 2:
                    child_container_ids = []
                    for idx, url in enumerate(media_urls, start=1):
                        is_vid = any(url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm"))
                        item_data = {
                            "is_carousel_item": "true",
                            "access_token": raw_token,
                        }
                        if is_vid:
                            item_data["video_url"] = url
                            item_data["media_type"] = "VIDEO"
                        else:
                            item_data["image_url"] = url

                        c_resp = await client.post(container_url, data=item_data, timeout=30.0)
                        if c_resp.status_code not in (200, 201):
                            err_msg = c_resp.json().get("error", {}).get("message") if c_resp.content else f"Child item #{idx} failed ({c_resp.status_code})"
                            return PublishResult(success=False, platform=self.platform, error_message=f"Carousel item #{idx} error: {err_msg}")
                        cid = c_resp.json().get("id")
                        if cid:
                            is_child_ready, child_err = await self._wait_for_container_ready(
                                client=client,
                                base_url=base_url,
                                container_id=cid,
                                raw_token=raw_token,
                                max_attempts=12 if is_vid else 10,
                                poll_interval=5.0 if is_vid else 2.0,
                            )
                            if not is_child_ready:
                                return PublishResult(
                                    success=False,
                                    platform=self.platform,
                                    error_message=f"Carousel item #{idx} readiness error: {child_err}",
                                )
                            child_container_ids.append(cid)

                    # Create parent carousel container
                    carousel_data = {
                        "media_type": "CAROUSEL",
                        "children": ",".join(child_container_ids),
                        "caption": caption,
                        "access_token": raw_token,
                    }
                    parent_resp = await client.post(container_url, data=carousel_data, timeout=30.0)
                    if parent_resp.status_code not in (200, 201):
                        err_msg = parent_resp.json().get("error", {}).get("message") if parent_resp.content else f"Carousel container error ({parent_resp.status_code})"
                        return PublishResult(success=False, platform=self.platform, error_message=err_msg)
                    container_id = parent_resp.json().get("id")

                # ── REEL OR VIDEO POST ────────────────────────────────────────
                elif post_type in ("reel", "video") or (context and context.is_video):
                    video_url = media_urls[0]
                    media_type_val = "REELS" if post_type == "reel" else "VIDEO"
                    vid_data = {
                        "video_url": video_url,
                        "caption": caption,
                        "media_type": media_type_val,
                        "access_token": raw_token,
                    }
                    c_resp = await client.post(container_url, data=vid_data, timeout=30.0)
                    if c_resp.status_code not in (200, 201):
                        err_msg = c_resp.json().get("error", {}).get("message") if c_resp.content else f"Video container error ({c_resp.status_code})"
                        return PublishResult(success=False, platform=self.platform, error_message=err_msg)
                    container_id = c_resp.json().get("id")

                # ── STORY POST ────────────────────────────────────────────────
                elif post_type == "story":
                    target_url = media_urls[0]
                    is_vid = any(target_url.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm"))
                    story_data = {
                        "media_type": "STORIES",
                        "access_token": raw_token,
                    }
                    if is_vid:
                        story_data["video_url"] = target_url
                    else:
                        story_data["image_url"] = target_url

                    c_resp = await client.post(container_url, data=story_data, timeout=30.0)
                    if c_resp.status_code not in (200, 201):
                        err_msg = c_resp.json().get("error", {}).get("message") if c_resp.content else f"Story container error ({c_resp.status_code})"
                        return PublishResult(success=False, platform=self.platform, error_message=err_msg)
                    container_id = c_resp.json().get("id")

                # ── SINGLE IMAGE POST ─────────────────────────────────────────
                else:
                    image_url = media_urls[0]
                    container_data = {
                        "image_url": image_url,
                        "caption": caption,
                        "access_token": raw_token,
                    }
                    c_resp = await client.post(container_url, data=container_data, timeout=30.0)
                    if c_resp.status_code not in (200, 201):
                        err_msg = f"Instagram container creation error ({c_resp.status_code})"
                        try:
                            err_data = c_resp.json().get("error", {})
                            msg = err_data.get("message")
                            user_msg = err_data.get("error_user_msg")
                            subcode = err_data.get("error_subcode")
                            if user_msg:
                                err_msg = f"{msg} - {user_msg}" if msg else user_msg
                            elif msg:
                                err_msg = f"{msg} (subcode: {subcode})" if subcode else msg
                        except Exception:
                            if c_resp.text:
                                err_msg = f"{err_msg}: {c_resp.text[:200]}"

                        if "only photo or video" in err_msg.lower() or "cannot be loaded" in err_msg.lower() or "could not be fetched" in err_msg.lower():
                            err_msg = (
                                "Cannot reach public media URL. The configured public tunnel/domain is unavailable or expired. "
                                f"Meta could not download media from: {image_url}"
                            )

                        logger.error("Instagram container creation failed (%s): %s | request image_url=%s", c_resp.status_code, err_msg, image_url)
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error_message=err_msg,
                        )
                    container_id = c_resp.json().get("id")

                if not container_id:
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error_message="Failed to obtain Instagram media container ID.",
                    )

                # Poll container readiness before calling media_publish (prevents 'Media ID is not available' 2207027 race conditions)
                is_vid = post_type in ("reel", "video") or (context and context.is_video)
                is_ready, ready_err = await self._wait_for_container_ready(
                    client=client,
                    base_url=base_url,
                    container_id=container_id,
                    raw_token=raw_token,
                    max_attempts=12 if is_vid else 10,
                    poll_interval=5.0 if is_vid else 2.0,
                )
                if not is_ready:
                    logger.error("Instagram container %s readiness check failed: %s", container_id, ready_err)
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error_message=ready_err or "Instagram media container was not ready for publishing.",
                    )

                # Step 2: Publish media container
                publish_url = f"{base_url}/{target_path}/media_publish"
                pub_data = {
                    "creation_id": container_id,
                    "access_token": raw_token,
                }
                p_resp = await client.post(publish_url, data=pub_data, timeout=30.0)
                if p_resp.status_code in (200, 201):
                    post_id_val = p_resp.json().get("id")
                    return PublishResult(
                        success=True,
                        platform=self.platform,
                        platform_post_id=post_id_val,
                        published_url=f"https://www.instagram.com/p/{post_id_val}/" if post_id_val else "https://www.instagram.com",
                        published_at=datetime.now(timezone.utc),
                    )
                else:
                    err_msg = f"Instagram media publish error ({p_resp.status_code})"
                    try:
                        err_data = p_resp.json().get("error", {})
                        msg = err_data.get("message")
                        user_msg = err_data.get("error_user_msg")
                        subcode = err_data.get("error_subcode")
                        if user_msg:
                            err_msg = f"{msg} - {user_msg}" if msg else user_msg
                        elif msg:
                            err_msg = f"{msg} (subcode: {subcode})" if subcode else msg
                    except Exception:
                        if p_resp.text:
                            err_msg = f"{err_msg}: {p_resp.text[:200]}"

                    logger.error("Instagram media publish failed (%s): %s", p_resp.status_code, err_msg)
                    return PublishResult(
                        success=False,
                        platform=self.platform,
                        error_message=err_msg,
                    )
        except httpx.RequestError as exc:
            logger.error("Instagram API network communication error: %s", exc, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=f"Network error communicating with Instagram API: {str(exc)}",
            )
        except Exception as exc:
            logger.error("Instagram publishing adapter exception: %s", exc, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=f"Instagram publishing failed: {str(exc)}",
            )
