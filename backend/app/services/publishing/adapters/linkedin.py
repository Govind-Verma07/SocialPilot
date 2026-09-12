"""
app/services/publishing/adapters/linkedin.py
-------------------------------------------
LinkedIn Publishing Adapter using UGC Post API (v2).
"""

from datetime import datetime, timezone
import httpx

from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.publishing.base import BasePlatformPublisher, PublishResult


class LinkedInPublisher(BasePlatformPublisher):
    platform = SocialPlatform.linkedin.value

    UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"

    async def publish(self, post: Post, social_account: SocialAccount) -> PublishResult:
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

        # 3. Construct UGC payload for text post
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": post.content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # 4. Make HTTP request
        try:
            async with httpx.AsyncClient() as client:
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
                err_msg = f"LinkedIn API error ({resp.status_code}): {resp.text}"
                try:
                    data = resp.json()
                    err_msg = data.get("message") or err_msg
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
