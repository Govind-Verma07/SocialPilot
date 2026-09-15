"""
app/services/publishing/adapters/facebook.py
-------------------------------------------
Facebook Publishing Adapter using Graph API.
Uses Page Access Token obtained via the connected Facebook user token
to publish posts to the Facebook Page feed.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger("socialpilot.publishing.facebook")

from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.publishing.base import BasePlatformPublisher, PublishResult


from app.services.publishing.media_resolver import PostPublishContext
from app.db.mongodb import get_mongo_db
from app.services.media_service import MediaService


class FacebookPublisher(BasePlatformPublisher):
    platform = SocialPlatform.facebook.value

    GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"

    async def publish(
        self,
        post: Post,
        social_account: SocialAccount,
        context: Optional[PostPublishContext] = None,
    ) -> PublishResult:
        raw_token = decrypt_token(social_account.access_token_encrypted) if getattr(social_account, "access_token_encrypted", None) else None
        if not raw_token:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Facebook access token is missing or invalid. Please reconnect your account.",
            )

        target_id = social_account.platform_account_id or "me"

        try:
            async with httpx.AsyncClient() as client:
                page_id = target_id
                page_access_token = raw_token

                # For real OAuth tokens, obtain Page Access Token from user's Facebook token
                if not raw_token.startswith(("mock-", "test-", "demo-")):
                    accounts_url = f"{self.GRAPH_BASE_URL}/me/accounts"
                    acc_resp = await client.get(accounts_url, params={"access_token": raw_token}, timeout=20.0)

                    if acc_resp.status_code != 200:
                        err_data = {}
                        try:
                            err_data = acc_resp.json().get("error", {})
                        except Exception:
                            pass
                        err_msg = err_data.get("message") or f"Failed to fetch Facebook Pages ({acc_resp.status_code})"
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error_message=err_msg,
                        )

                    pages = acc_resp.json().get("data", [])
                    target_page = None

                    # Find page matching platform_account_id
                    if target_id and target_id != "me":
                        for p in pages:
                            if str(p.get("id")) == str(target_id):
                                target_page = p
                                break

                    # If not matched directly, fallback to first managed page
                    if not target_page and pages:
                        target_page = pages[0]

                    # If still not found but a specific target_id exists, try direct page token query
                    if not target_page and target_id and target_id != "me":
                        page_token_resp = await client.get(
                            f"{self.GRAPH_BASE_URL}/{target_id}",
                            params={"fields": "access_token,name", "access_token": raw_token},
                            timeout=20.0,
                        )
                        if page_token_resp.status_code == 200:
                            target_page = page_token_resp.json()

                    if not target_page or not target_page.get("access_token"):
                        return PublishResult(
                            success=False,
                            platform=self.platform,
                            error_message=(
                                "No Facebook Page found with publishing permissions for this account. "
                                "Ensure you manage a Facebook Page and granted pages_manage_posts and pages_read_engagement permissions."
                            ),
                        )

                    page_id = target_page.get("id") or target_id
                    page_access_token = target_page.get("access_token")

                # Step 2: Publish according to media format
                post_type = (context.post_type if context else (post.post_type or "text")).lower()
                has_media = bool(context and context.has_media)
                message_text = post.content or ""
                mongo_db = get_mongo_db()

                # ── CAROUSEL POST (Multi-photo upload) ─────────────────────────
                if has_media and post_type == "carousel" and len(context.media_items) >= 2:
                    photo_ids = []
                    photos_url = f"{self.GRAPH_BASE_URL}/{page_id}/photos"
                    for it in context.media_items:
                        data_bytes = None
                        if mongo_db is not None and it.media_id and not it.media_id.startswith("legacy_"):
                            try:
                                data_bytes = await MediaService.get_media_binary_bytes(mongo_db, it.media_id)
                            except Exception as be:
                                logger.warning("Could not read binary bytes for Facebook carousel item: %s", be)

                        if data_bytes:
                            files = {"source": (it.original_filename or "photo.jpg", data_bytes, it.mime_type or "image/jpeg")}
                            p_data = {"published": "false", "access_token": page_access_token}
                            up_resp = await client.post(photos_url, data=p_data, files=files, timeout=30.0)
                        else:
                            p_data = {"url": it.public_url, "published": "false", "access_token": page_access_token}
                            up_resp = await client.post(photos_url, data=p_data, timeout=30.0)

                        if up_resp.status_code in (200, 201):
                            pid = up_resp.json().get("id")
                            if pid:
                                photo_ids.append(pid)
                        else:
                            err_body = up_resp.text[:200]
                            logger.error("Facebook carousel photo upload failed: %s %s", up_resp.status_code, err_body)

                    # Attach uploaded photos to feed post
                    feed_url = f"{self.GRAPH_BASE_URL}/{page_id}/feed"
                    feed_payload = {
                        "message": message_text,
                        "access_token": page_access_token,
                    }
                    for idx, pid in enumerate(photo_ids):
                        feed_payload[f"attached_media[{idx}]"] = f'{{"media_fbid":"{pid}"}}'
                    resp = await client.post(feed_url, data=feed_payload, timeout=30.0)

                # ── VIDEO OR REEL POST (Direct video upload) ───────────────────
                elif has_media and (post_type in ("video", "reel") or context.is_video):
                    vid_item = context.primary_media
                    videos_url = f"{self.GRAPH_BASE_URL}/{page_id}/videos"
                    v_data = {
                        "description": message_text,
                        "access_token": page_access_token,
                    }
                    data_bytes = None
                    if mongo_db is not None and vid_item.media_id and not vid_item.media_id.startswith("legacy_"):
                        try:
                            data_bytes = await MediaService.get_media_binary_bytes(mongo_db, vid_item.media_id)
                        except Exception as be:
                            logger.warning("Could not read binary bytes for Facebook video: %s", be)

                    if data_bytes:
                        files = {"source": (vid_item.original_filename or "video.mp4", data_bytes, vid_item.mime_type or "video/mp4")}
                        resp = await client.post(videos_url, data=v_data, files=files, timeout=60.0)
                    else:
                        v_data["file_url"] = vid_item.public_url
                        resp = await client.post(videos_url, data=v_data, timeout=60.0)

                # ── SINGLE IMAGE OR STORY POST (Direct photo upload) ───────────
                elif has_media:
                    img_item = context.primary_media
                    photos_url = f"{self.GRAPH_BASE_URL}/{page_id}/photos"
                    p_data = {
                        "caption": message_text,
                        "access_token": page_access_token,
                    }
                    data_bytes = None
                    if mongo_db is not None and img_item.media_id and not img_item.media_id.startswith("legacy_"):
                        try:
                            data_bytes = await MediaService.get_media_binary_bytes(mongo_db, img_item.media_id)
                        except Exception as be:
                            logger.warning("Could not read binary bytes for Facebook photo: %s", be)

                    if data_bytes:
                        files = {"source": (img_item.original_filename or "photo.jpg", data_bytes, img_item.mime_type or "image/jpeg")}
                        resp = await client.post(photos_url, data=p_data, files=files, timeout=30.0)
                    else:
                        p_data["url"] = img_item.public_url
                        resp = await client.post(photos_url, data=p_data, timeout=30.0)

                # ── TEXT-ONLY POST (Page feed) ────────────────────────────────
                else:
                    publish_url = f"{self.GRAPH_BASE_URL}/{page_id}/feed"
                    payload = {
                        "message": message_text,
                        "access_token": page_access_token,
                    }
                    resp = await client.post(publish_url, data=payload, timeout=30.0)

            if resp.status_code in (200, 201):
                data = resp.json()
                post_id = data.get("id")
                published_url = f"https://www.facebook.com/{post_id}" if post_id else "https://www.facebook.com"
                return PublishResult(
                    success=True,
                    platform=self.platform,
                    platform_post_id=post_id,
                    published_url=published_url,
                    published_at=datetime.now(timezone.utc),
                )
            elif resp.status_code in (401, 190):
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="Facebook session/token has expired. Please reconnect your Facebook account.",
                )
            else:
                err_msg = f"Facebook Graph API error ({resp.status_code})"
                try:
                    data = resp.json()
                    err_data = data.get("error", {})
                    err_msg = err_data.get("message") or err_msg
                    subcode = err_data.get("error_subcode")
                    if subcode:
                        err_msg += f" (subcode: {subcode})"
                except Exception:
                    if resp.text:
                        err_msg = f"{err_msg}: {resp.text[:200]}"

                logger.error("Facebook Graph API error response: %s (status %s)", err_msg, resp.status_code)
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=err_msg,
                )
        except httpx.RequestError as exc:
            logger.error("Facebook API network communication error: %s", exc, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=f"Network error communicating with Facebook Graph API: {str(exc)}",
            )
        except Exception as exc:
            logger.error("Facebook publishing adapter exception: %s", exc, exc_info=True)
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=f"Facebook publishing failed: {str(exc)}",
            )
