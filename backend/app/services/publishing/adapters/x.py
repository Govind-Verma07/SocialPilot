"""
app/services/publishing/adapters/x.py
------------------------------------
X (Twitter) Publishing Adapter using X API v2 Tweets endpoint.
"""

from datetime import datetime, timezone, timedelta
import logging
from typing import Optional
import httpx

from app.core.encryption import decrypt_token, encrypt_token
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.publishing.base import BasePlatformPublisher, PublishResult
from app.services.publishing.media_resolver import PostPublishContext

logger = logging.getLogger("uvicorn.error")


class XPublisher(BasePlatformPublisher):
    platform = SocialPlatform.x.value

    TWEETS_URL = "https://api.twitter.com/2/tweets"

    async def _refresh_account_token(self, social_account: SocialAccount) -> Optional[str]:
        """
        Refresh the X OAuth 2.0 access token using the stored refresh token.
        Persists the new rotated tokens to PostgreSQL and updates the social_account instance.
        """
        if not social_account.refresh_token_encrypted:
            return None

        refresh_token = decrypt_token(social_account.refresh_token_encrypted)
        if not refresh_token:
            return None

        try:
            from app.services.social_providers.x import XProvider
            from app.db.session import SessionLocal

            provider = XProvider()
            token_data = await provider.refresh_access_token(refresh_token)
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 7200)

            if not new_access_token:
                logger.warning("X token refresh did not return an access token.")
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
                    acc.refresh_token_encrypted = social_account.refresh_token_encrypted
                    acc.token_expires_at = social_account.token_expires_at
                    acc.updated_at = now
                    db.commit()
                    logger.info("Successfully refreshed and saved X OAuth 2.0 tokens for account %s", social_account.id)
            finally:
                db.close()

            return new_access_token
        except Exception as exc:
            logger.warning("Failed to refresh X OAuth 2.0 access token: %s", exc)
            return None

    async def publish(
        self,
        post: Post,
        social_account: SocialAccount,
        context: Optional[PostPublishContext] = None,
    ) -> PublishResult:
        now = datetime.now(timezone.utc)
        refreshed = False

        # 1. Proactively refresh if expired or about to expire in next 2 minutes
        if social_account.token_expires_at and social_account.token_expires_at <= now + timedelta(minutes=2):
            new_token = await self._refresh_account_token(social_account)
            if new_token:
                raw_token = new_token
                refreshed = True
            else:
                raw_token = decrypt_token(social_account.access_token_encrypted)
        else:
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

            # 2. Reactively refresh on 401 if not already refreshed
            if resp.status_code == 401 and not refreshed:
                logger.info("X API returned 401. Attempting automatic token refresh...")
                new_token = await self._refresh_account_token(social_account)
                if new_token:
                    headers["Authorization"] = f"Bearer {new_token}"
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
            elif resp.status_code == 402:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="X (Twitter) API credits depleted (402): Your X Developer account has exhausted its tweet posting credits. Please check your X Developer Portal quota/billing.",
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

