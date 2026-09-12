"""
app/services/publishing/service.py
----------------------------------
Publishing service orchestrator for Phase 5.
Coordinates publishing a post to all associated social accounts and recording outcomes.
"""

from datetime import datetime, timezone
from typing import List, Tuple
from sqlalchemy.orm import Session

from app.models.enums import PostStatus, PublishingLogEventType
from app.models.post import Post
from app.models.post_publish_result import PostPublishResult
from app.models.publishing_log import PublishingLog
from app.models.social_account import SocialAccount
from app.services.publishing.adapters import get_publisher
from app.services.publishing.base import PublishResult


class PublishingService:
    @staticmethod
    async def publish_post(db: Session, post: Post) -> Tuple[Post, List[PostPublishResult]]:
        """
        Publishes a post across all attached social accounts independently.
        Updates Post status (published if any succeeded, failed if all failed)
        and persists PostPublishResult records.
        """
        # Ensure post has attached social accounts
        attached_accounts = [psa.social_account for psa in post.social_accounts if psa.social_account]
        if not attached_accounts:
            raise ValueError("Post has no attached social accounts to publish to.")

        results: List[PostPublishResult] = []
        any_success = False

        for account in attached_accounts:
            platform_str = account.platform.value if hasattr(account.platform, "value") else str(account.platform)
            try:
                publisher = get_publisher(platform_str)
                res: PublishResult = await publisher.publish(post, account)
            except Exception as exc:
                res = PublishResult(
                    success=False,
                    platform=platform_str,
                    error_message=f"Publishing failed: {str(exc)}",
                )

            status_str = "published" if res.success else "failed"
            if res.success:
                any_success = True

            record = PostPublishResult(
                post_id=post.id,
                social_account_id=account.id,
                platform=platform_str,
                status=status_str,
                platform_post_id=res.platform_post_id,
                published_url=res.published_url,
                error_message=res.error_message,
                published_at=res.published_at or (datetime.now(timezone.utc) if res.success else None),
            )
            db.add(record)
            results.append(record)

            # Phase 9: Record audit PublishingLog
            log_entry = PublishingLog(
                post_id=post.id,
                social_account_id=account.id,
                platform=platform_str,
                event_type=PublishingLogEventType.published.value if res.success else PublishingLogEventType.failed.value,
                status=status_str,
                attempt_number=1,
                platform_post_id=res.platform_post_id,
                published_url=res.published_url,
                error_message=res.error_message,
                created_at=datetime.now(timezone.utc),
            )
            db.add(log_entry)

        # Update Post status and published timestamp
        now = datetime.now(timezone.utc)
        if any_success:
            post.status = PostStatus.published.value
            post.published_at = now
        else:
            post.status = PostStatus.failed.value

        post.updated_at = now
        db.commit()
        db.refresh(post)

        # Generate and persist rich audit log with real post information to disk & cache
        try:
            from app.services.publishing.log_generator import generate_post_audit_log_content
            generate_post_audit_log_content(db, post)
        except Exception as log_exc:
            import logging
            logging.getLogger("socialpilot.publishing").warning(f"Could not write log file for post #{post.id}: {log_exc}")

        return post, results
