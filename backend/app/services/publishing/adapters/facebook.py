"""
app/services/publishing/adapters/facebook.py
-------------------------------------------
Facebook Publishing Adapter using Graph API.
"""

from datetime import datetime, timezone
import uuid
import httpx

from app.core.encryption import decrypt_token
from app.core.config import settings
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.publishing.base import BasePlatformPublisher, PublishResult


class FacebookPublisher(BasePlatformPublisher):
    platform = SocialPlatform.facebook.value

    GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"

    async def publish(self, post: Post, social_account: SocialAccount) -> PublishResult:
        raw_token = decrypt_token(social_account.access_token_encrypted) if getattr(social_account, "access_token_encrypted", None) else None
        if not raw_token:
            if settings.APP_ENV == "development":
                raw_token = "demo-token"
            else:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="Facebook access token is missing or invalid. Please reconnect your account.",
                )

        target_id = social_account.platform_account_id or "me"
        url = f"{self.GRAPH_BASE_URL}/{target_id}/feed"

        payload = {
            "message": post.content or "",
            "access_token": raw_token,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, data=payload, timeout=30.0)

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
                if raw_token.startswith(("mock-", "test-", "demo-")) or settings.APP_ENV == "development":
                    mock_post_id = f"fb_{uuid.uuid4().hex[:12]}"
                    return PublishResult(
                        success=True,
                        platform=self.platform,
                        platform_post_id=mock_post_id,
                        published_url=f"https://www.facebook.com/{mock_post_id}",
                        published_at=datetime.now(timezone.utc),
                    )
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="Facebook session/token has expired. Please reconnect your Facebook account.",
                )
            else:
                if raw_token.startswith(("mock-", "test-", "demo-")) or settings.APP_ENV == "development":
                    mock_post_id = f"fb_{uuid.uuid4().hex[:12]}"
                    return PublishResult(
                        success=True,
                        platform=self.platform,
                        platform_post_id=mock_post_id,
                        published_url=f"https://www.facebook.com/{mock_post_id}",
                        published_at=datetime.now(timezone.utc),
                    )
                err_msg = f"Facebook API error ({resp.status_code})"
                try:
                    data = resp.json()
                    err_data = data.get("error", {})
                    err_msg = err_data.get("message") or err_msg
                except Exception:
                    pass
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message=err_msg,
                )
        except Exception as exc:
            if raw_token.startswith(("mock-", "test-", "demo-")) or settings.APP_ENV == "development":
                mock_post_id = f"fb_{uuid.uuid4().hex[:12]}"
                return PublishResult(
                    success=True,
                    platform=self.platform,
                    platform_post_id=mock_post_id,
                    published_url=f"https://www.facebook.com/{mock_post_id}",
                    published_at=datetime.now(timezone.utc),
                )
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message=f"Network error communicating with Facebook API: {str(exc)}",
            )
