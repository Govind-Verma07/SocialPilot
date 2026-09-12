"""
app/services/publishing/adapters/x.py
------------------------------------
X (Twitter) Publishing Adapter using X API v2 Tweets endpoint.
"""

from datetime import datetime, timezone
import httpx

from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.publishing.base import BasePlatformPublisher, PublishResult


class XPublisher(BasePlatformPublisher):
    platform = SocialPlatform.x.value

    TWEETS_URL = "https://api.twitter.com/2/tweets"

    async def publish(self, post: Post, social_account: SocialAccount) -> PublishResult:
        raw_token = decrypt_token(social_account.access_token_encrypted)
        if not raw_token:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="X (Twitter) access token is missing or invalid. Please reconnect your account.",
            )

        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "text": post.content,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.TWEETS_URL, json=payload, headers=headers, timeout=30.0)

            if resp.status_code in (200, 201):
                data = resp.json().get("data", {})
                tweet_id = data.get("id")
                username = social_account.account_username or "i"
                return PublishResult(
                    success=True,
                    platform=self.platform,
                    platform_post_id=tweet_id,
                    published_url=f"https://x.com/{username}/status/{tweet_id}" if tweet_id else "https://x.com",
                    published_at=datetime.now(timezone.utc),
                )
            elif resp.status_code == 401:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="X (Twitter) token is invalid or expired (401). Please reconnect your account.",
                )
            elif resp.status_code == 403:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="X (Twitter) permission denied (403). Ensure 'tweet.write' scope is granted.",
                )
            else:
                err_msg = f"X API error ({resp.status_code}): {resp.text}"
                try:
                    data = resp.json()
                    err_msg = data.get("detail") or data.get("title") or err_msg
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
                error_message=f"Network error communicating with X API: {str(exc)}",
            )
