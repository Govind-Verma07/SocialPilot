"""
app/services/publishing/adapters/instagram.py
--------------------------------------------
Instagram Publishing Adapter using Instagram Graph API.
Note: Instagram Graph API requires media (image or video) for publishing. Text-only posts are unsupported.
"""

from datetime import datetime, timezone
import httpx

from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.publishing.base import BasePlatformPublisher, PublishResult


class InstagramPublisher(BasePlatformPublisher):
    platform = SocialPlatform.instagram.value

    GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"

    async def publish(self, post: Post, social_account: SocialAccount) -> PublishResult:
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

        # Content requirement check: Instagram requires media (fallback to visual card if text-only)
        media_urls = post.media_urls or []
        image_url = media_urls[0] if media_urls else "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1080&auto=format&fit=crop&q=80"

        try:
            async with httpx.AsyncClient() as client:
                # Step 1: Create media container
                container_url = f"{self.GRAPH_BASE_URL}/{ig_user_id}/media"
                container_data = {
                    "image_url": image_url,
                    "caption": post.content or "",
                    "access_token": raw_token,
                }
                c_resp = await client.post(container_url, data=container_data, timeout=30.0)
                if c_resp.status_code not in (200, 201):
                    err_msg = f"Instagram container creation error ({c_resp.status_code})"
                    try:
                        err_msg = c_resp.json().get("error", {}).get("message") or err_msg
                    except Exception:
                        pass
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

                # Step 2: Publish media container
                publish_url = f"{self.GRAPH_BASE_URL}/{ig_user_id}/media_publish"
                pub_data = {
                    "creation_id": container_id,
                    "access_token": raw_token,
                }
                p_resp = await client.post(publish_url, data=pub_data, timeout=30.0)
                if p_resp.status_code in (200, 201):
                    post_id = p_resp.json().get("id")
                    return PublishResult(
                        success=True,
                        platform=self.platform,
                        platform_post_id=post_id,
                        published_url=f"https://www.instagram.com/p/{post_id}/" if post_id else "https://www.instagram.com",
                        published_at=datetime.now(timezone.utc),
                    )
                else:
                    err_msg = f"Instagram media publish error ({p_resp.status_code})"
                    try:
                        err_msg = p_resp.json().get("error", {}).get("message") or err_msg
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
                error_message=f"Network error communicating with Instagram API: {str(exc)}",
            )
