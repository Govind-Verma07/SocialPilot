from datetime import datetime, timezone
import logging
from typing import Optional, List
import httpx

from app.core.encryption import decrypt_token
from app.db.mongodb import get_mongo_db
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.media_service import MediaService
from app.services.publishing.base import BasePlatformPublisher, PublishResult
from app.services.publishing.media_resolver import PostPublishContext

logger = logging.getLogger("uvicorn.error")


class LinkedInPublisher(BasePlatformPublisher):
    platform = SocialPlatform.linkedin.value

    UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
    ASSETS_REGISTER_URL = "https://api.linkedin.com/v2/assets?action=registerUpload"

    async def _upload_asset(
        self,
        client: httpx.AsyncClient,
        raw_token: str,
        author_urn: str,
        binary_data: bytes,
        is_video: bool = False,
    ) -> Optional[str]:
        """
        Registers an asset upload with LinkedIn and uploads binary bytes.
        Returns the asset URN (e.g., urn:li:digitalmediaAsset:...) or None on error.
        """
        recipe = (
            "urn:li:digitalmediaRecipe:feedshare-video"
            if is_video
            else "urn:li:digitalmediaRecipe:feedshare-image"
        )
        register_payload = {
            "registerUploadRequest": {
                "recipes": [recipe],
                "owner": author_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }
        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        resp = await client.post(self.ASSETS_REGISTER_URL, json=register_payload, headers=headers, timeout=30.0)
        if resp.status_code not in (200, 201):
            logger.error("LinkedIn registerUpload failed (%s): %s", resp.status_code, resp.text)
            return None

        data = resp.json().get("value", {})
        upload_mech = data.get("uploadMechanism", {}).get(
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {}
        )
        upload_url = upload_mech.get("uploadUrl")
        asset_urn = data.get("asset")

        if not upload_url or not asset_urn:
            logger.error("LinkedIn registerUpload did not return uploadUrl or asset URN")
            return None

        content_type = "video/mp4" if is_video else "image/jpeg"
        upload_resp = await client.put(
            upload_url,
            content=binary_data,
            headers={
                "Authorization": f"Bearer {raw_token}",
                "Content-Type": content_type,
            },
            timeout=60.0,
        )
        if upload_resp.status_code not in (200, 201):
            logger.error("LinkedIn media binary upload failed (%s): %s", upload_resp.status_code, upload_resp.text)
            return None

        return asset_urn

    async def publish(
        self,
        post: Post,
        social_account: SocialAccount,
        context: Optional[PostPublishContext] = None,
    ) -> PublishResult:
        # 1. Retrieve & decrypt access token
        raw_token = decrypt_token(social_account.access_token_encrypted)
        if not raw_token:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="LinkedIn access token is missing or invalid. Please reconnect your account.",
            )

        # 2. Format author URN: urn:li:person:{id}
        account_id = social_account.platform_account_id
        if not account_id:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="LinkedIn account ID is missing. Please reconnect your account.",
            )

        if account_id.startswith("urn:li:"):
            author_urn = account_id
        else:
            author_urn = f"urn:li:person:{account_id}"

        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # 3. Determine if media is attached
        has_media = bool(context and context.has_media)
        media_list = []
        share_media_category = "NONE"

        try:
            async with httpx.AsyncClient() as client:
                if has_media and context:
                    mongo_db = get_mongo_db()
                    is_video_post = context.has_video

                    for item in context.media_items:
                        binary_data = None
                        if mongo_db is not None and item.media_id:
                            binary_data = await MediaService.get_media_binary_bytes(mongo_db, item.media_id)
                        if not binary_data and item.public_url:
                            r = await client.get(item.public_url, timeout=30.0)
                            if r.status_code == 200:
                                binary_data = r.content

                        if binary_data:
                            item_is_video = item.mime_type.startswith("video/") or (item.format in ("video", "reel"))
                            asset_urn = await self._upload_asset(
                                client=client,
                                raw_token=raw_token,
                                author_urn=author_urn,
                                binary_data=binary_data,
                                is_video=item_is_video,
                            )
                            if asset_urn:
                                media_list.append({
                                    "status": "READY",
                                    "description": {
                                        "text": (post.content or "")[:200]
                                    },
                                    "media": asset_urn,
                                    "title": {
                                        "text": (item.filename or "Media")[:100]
                                    }
                                })
                                if item_is_video:
                                    break  # LinkedIn supports one video per post

                    if media_list:
                        share_media_category = "VIDEO" if is_video_post else "IMAGE"
                    else:
                        logger.warning("Failed to upload media assets for LinkedIn; falling back to text commentary.")

                # Construct UGC payload
                share_content = {
                    "shareCommentary": {
                        "text": post.content or ""
                    },
                    "shareMediaCategory": share_media_category,
                }
                if media_list:
                    share_content["media"] = media_list

                payload = {
                    "author": author_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": share_content
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                    }
                }

                # 4. Make HTTP request
                resp = await client.post(self.UGC_POSTS_URL, json=payload, headers=headers, timeout=30.0)

            if resp.status_code in (200, 201):
                data = resp.json()
                post_urn = data.get("id") or resp.headers.get("x-restli-id", "")
                published_url = f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else "https://www.linkedin.com/feed/"
                return PublishResult(
                    success=True,
                    platform=self.platform,
                    platform_post_id=post_urn,
                    published_url=published_url,
                    published_at=datetime.now(timezone.utc),
                )
            elif resp.status_code == 401:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="LinkedIn authentication expired (401). Please reconnect your LinkedIn account.",
                )
            elif resp.status_code == 403:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="LinkedIn permission denied (403). Ensure 'w_member_social' scope is granted.",
                )
            else:
                err_msg = f"LinkedIn API error ({resp.status_code})"
                try:
                    data = resp.json()
                    raw_msg = data.get("message") or ""
                    if "Content is a duplicate" in raw_msg:
                        err_msg = "LinkedIn rejected duplicate post: Identical content was recently posted. Please vary your post text."
                    elif raw_msg:
                        if ": " in raw_msg:
                            err_msg = raw_msg.split(": ", 1)[1]
                        else:
                            err_msg = raw_msg
                    else:
                        err_msg = f"LinkedIn API error ({resp.status_code}): {resp.text}"
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
                error_message=f"Network error communicating with LinkedIn API: {str(exc)}",
            )
