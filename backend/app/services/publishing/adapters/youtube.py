"""
app/services/publishing/adapters/youtube.py
------------------------------------------
YouTube Publishing Adapter.
Supports video uploads via YouTube Data API v3 videos insert.
Text-only posts are not supported by the YouTube API and are marked as SKIPPED.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Optional
import httpx

from app.core.encryption import decrypt_token, encrypt_token
from app.db.mongodb import get_mongo_db
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.media_service import MediaService
from app.services.publishing.base import BasePlatformPublisher, PublishResult
from app.services.publishing.media_resolver import PostPublishContext

logger = logging.getLogger("uvicorn.error")


class YouTubePublisher(BasePlatformPublisher):
    platform = SocialPlatform.youtube.value

    INITIATE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    METADATA_INSERT_URL = "https://www.googleapis.com/youtube/v3/videos?part=snippet,status"

    async def _refresh_account_token(self, social_account: SocialAccount) -> Optional[str]:
        """
        Refresh the YouTube (Google OAuth 2.0) access token using the stored refresh token.
        Persists the new token to PostgreSQL and updates the in-memory social_account instance.
        """
        if not getattr(social_account, "refresh_token_encrypted", None):
            return None

        refresh_token = decrypt_token(social_account.refresh_token_encrypted)
        if not refresh_token:
            return None

        try:
            from app.services.social_providers.youtube import YouTubeProvider
            from app.db.session import SessionLocal

            provider = YouTubeProvider()
            token_data = await provider.refresh_access_token(refresh_token)
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)

            if not new_access_token:
                logger.warning("YouTube token refresh did not return an access token.")
                return None

            now = datetime.now(timezone.utc)
            expires_at = datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc)

            # Update in-memory instance
            social_account.access_token_encrypted = encrypt_token(new_access_token)
            if new_refresh_token:
                social_account.refresh_token_encrypted = encrypt_token(new_refresh_token)
            social_account.token_expires_at = expires_at

            # Persist to database
            db = SessionLocal()
            try:
                acc = db.query(SocialAccount).filter(SocialAccount.id == social_account.id).first()
                if acc:
                    acc.access_token_encrypted = social_account.access_token_encrypted
                    if new_refresh_token:
                        acc.refresh_token_encrypted = social_account.refresh_token_encrypted
                    acc.token_expires_at = social_account.token_expires_at
                    acc.updated_at = now
                    db.commit()
                    logger.info("Successfully refreshed and saved YouTube OAuth tokens for account %s", social_account.id)
            finally:
                db.close()

            return new_access_token
        except Exception as exc:
            logger.warning("Failed to refresh YouTube OAuth access token: %s", exc)
            return None

    async def publish(
        self,
        post: Post,
        social_account: SocialAccount,
        context: Optional[PostPublishContext] = None,
    ) -> PublishResult:
        # Content requirement check: YouTube requires a video
        video_item = None
        if context and context.media_items:
            for item in context.media_items:
                if item.mime_type.startswith("video/") or item.format in ("video", "reel") or item.filename.lower().endswith((".mp4", ".mov", ".webm", ".mkv", ".avi")):
                    video_item = item
                    break

        has_video = bool(video_item) or (post.post_type in ("video", "reel")) or any(
            url.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")) for url in (post.media_urls or [])
        )

        if not has_video:
            if (context and context.has_media) or (post.post_type == "image") or bool(post.media_urls):
                err_msg = "YouTube requires video media; image-only posts cannot be published to YouTube."
            else:
                err_msg = "YouTube does not support text-only posts. Please attach a video."
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=err_msg,
                skipped=True,
            )

        now = datetime.now(timezone.utc)
        refreshed = False

        expires_at = getattr(social_account, "token_expires_at", None)
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # Proactively refresh token if expired or expiring within 2 minutes
        if expires_at and expires_at <= now + timedelta(minutes=2):
            new_token = await self._refresh_account_token(social_account)
            if new_token:
                raw_token = new_token
                refreshed = True
            else:
                raw_token = decrypt_token(social_account.access_token_encrypted) if getattr(social_account, "access_token_encrypted", None) else None
        else:
            raw_token = decrypt_token(social_account.access_token_encrypted) if getattr(social_account, "access_token_encrypted", None) else None

        if not raw_token and getattr(social_account, "refresh_token_encrypted", None):
            new_token = await self._refresh_account_token(social_account)
            if new_token:
                raw_token = new_token
                refreshed = True

        if not raw_token:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="YouTube access token is missing or invalid. Please reconnect your account.",
            )

        snippet_data = {
            "snippet": {
                "title": (post.content or "SocialPilot Video")[:100],
                "description": post.content or "",
            },
            "status": {
                "privacyStatus": "public",
            },
        }

        # Try to load binary bytes if available
        binary_data = None
        mongo_db = get_mongo_db()
        if mongo_db is not None and video_item and video_item.media_id:
            try:
                binary_data = await MediaService.get_media_binary_bytes(mongo_db, video_item.media_id)
            except Exception as e:
                logger.warning("Could not read binary data for YouTube upload: %s", e)

        async def _do_upload(client: httpx.AsyncClient, token: str) -> httpx.Response:
            if binary_data:
                init_headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": video_item.mime_type if video_item else "video/mp4",
                    "X-Upload-Content-Length": str(len(binary_data)),
                }
                init_resp = await client.post(
                    self.INITIATE_UPLOAD_URL,
                    json=snippet_data,
                    headers=init_headers,
                    timeout=30.0,
                )
                if init_resp.status_code in (200, 201):
                    upload_location = init_resp.headers.get("Location")
                    if upload_location:
                        return await client.put(
                            upload_location,
                            content=binary_data,
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": video_item.mime_type if video_item else "video/mp4",
                            },
                            timeout=120.0,
                        )
                    return init_resp
                return init_resp
            else:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                return await client.post(self.METADATA_INSERT_URL, json=snippet_data, headers=headers, timeout=30.0)

        try:
            async with httpx.AsyncClient() as client:
                resp = await _do_upload(client, raw_token)

                # Reactively refresh on 401 if not already refreshed
                if resp.status_code == 401 and not refreshed:
                    logger.info("YouTube API returned 401. Attempting automatic token refresh...")
                    new_token = await self._refresh_account_token(social_account)
                    if new_token:
                        raw_token = new_token
                        refreshed = True
                        resp = await _do_upload(client, raw_token)

            if resp.status_code in (200, 201):
                video_id = resp.json().get("id")
                return PublishResult(
                    success=True,
                    platform=self.platform,
                    platform_post_id=video_id,
                    published_url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "https://www.youtube.com",
                    published_at=datetime.now(timezone.utc),
                )
            elif resp.status_code == 401:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="YouTube token is expired or invalid (401). Please reconnect your YouTube account.",
                )
            else:
                err_msg = f"YouTube API error ({resp.status_code})"
                try:
                    err_msg = resp.json().get("error", {}).get("message") or err_msg
                except Exception:
                    pass
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=err_msg,
                )
        except Exception as exc:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=f"Network error communicating with YouTube API: {str(exc)}",
            )
