"""
app/services/publishing/adapters/pinterest.py
--------------------------------------------
Pinterest Publishing Adapter using Pinterest API v5 Pins endpoint.
Supports:
1. Pins with custom uploaded images or videos.
Text-only posts are not supported by Pinterest and are marked as SKIPPED.
"""

from typing import Optional
from datetime import datetime, timezone
import httpx

from app.core.encryption import decrypt_token
from app.models.enums import SocialPlatform
from app.models.post import Post
from app.models.social_account import SocialAccount
from app.services.publishing.base import BasePlatformPublisher, PublishResult
from app.services.publishing.media_resolver import PostPublishContext


class PinterestPublisher(BasePlatformPublisher):
    platform = SocialPlatform.pinterest.value

    PINS_URL = "https://api.pinterest.com/v5/pins"
    BOARDS_URL = "https://api.pinterest.com/v5/boards"

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
                error_message="Pinterest access token is missing or invalid. Please reconnect your account.",
            )

        # Content requirement check: Pinterest requires image or video media
        image_url = None
        if context and context.primary_item and context.primary_item.public_url:
            image_url = context.primary_item.public_url
        elif post.media_urls:
            image_url = post.media_urls[0]

        if not image_url:
            return PublishResult(
                success=False,
                platform=self.platform,
                error_message="Pinterest requires image or video media.",
                skipped=True,
            )

        headers = {
            "Authorization": f"Bearer {raw_token}",
            "Content-Type": "application/json",
        }

        # Determine board ID
        board_id = getattr(social_account, "platform_account_id", None)

        try:
            async with httpx.AsyncClient() as client:
                # If board_id is missing or placeholder, fetch or create a board
                if not board_id or board_id in ("default", "none"):
                    try:
                        b_resp = await client.get(self.BOARDS_URL, headers=headers, timeout=15.0)
                        if b_resp.status_code == 200:
                            boards = b_resp.json().get("items", [])
                            if boards:
                                board_id = boards[0].get("id")
                            else:
                                # Create a default board
                                create_board_resp = await client.post(
                                    self.BOARDS_URL,
                                    json={"name": "SocialPilot Posts", "privacy": "PUBLIC"},
                                    headers=headers,
                                    timeout=15.0,
                                )
                                if create_board_resp.status_code in (200, 201):
                                    board_id = create_board_resp.json().get("id")
                    except Exception:
                        board_id = "default"

                payload = {
                    "board_id": board_id or "default",
                    "title": (post.content or "SocialPilot Pin")[:100],
                    "description": post.content or "",
                    "media_source": {
                        "source_type": "image_url",
                        "url": image_url,
                    },
                }

                resp = await client.post(self.PINS_URL, json=payload, headers=headers, timeout=30.0)

            if resp.status_code in (200, 201):
                data = resp.json()
                pin_id = data.get("id")
                return PublishResult(
                    success=True,
                    platform=self.platform,
                    platform_post_id=pin_id,
                    published_url=f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else "https://www.pinterest.com",
                    published_at=datetime.now(timezone.utc),
                )
            elif resp.status_code == 401:
                return PublishResult(
                    success=False,
                    platform=self.platform,
                    error_message="Pinterest access token is expired or unauthorized (401). Please reconnect your Pinterest account.",
                )
            else:
                err_msg = f"Pinterest API error ({resp.status_code})"
                try:
                    err_msg = resp.json().get("message") or err_msg
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
                error_message=f"Network error communicating with Pinterest API: {str(exc)}",
            )
