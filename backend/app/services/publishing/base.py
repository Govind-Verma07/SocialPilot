"""
app/services/publishing/base.py
-------------------------------
Base abstractions and standardized data structures for Phase 5 social media publishing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.models.post import Post
from app.models.social_account import SocialAccount


@dataclass
class PublishResult:
    """
    Standardized result returned by any platform publisher adapter.
    """
    success: bool
    platform: str
    platform_post_id: Optional[str] = None
    published_url: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None


class BasePlatformPublisher(ABC):
    """
    Abstract base class for platform-specific publishers.
    """
    platform: str

    @abstractmethod
    async def publish(self, post: Post, social_account: SocialAccount) -> PublishResult:
        """
        Publish the given post using the credentials of the specified social account.
        Must return a normalized PublishResult without raising unhandled platform exceptions.
        """
        pass
