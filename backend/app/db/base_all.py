"""
app/db/base_all.py
------------------
Import aggregator for Alembic and startup table-creation.

This module imports Base AND all ORM models so that:
  - Alembic's `target_metadata = Base.metadata` sees every table.
  - `Base.metadata.create_all()` creates every table.

Usage in alembic/env.py:
    from app.db.base_all import Base

Usage in main.py startup:
    from app.db.base_all import Base  # ensures all models registered

DO NOT use this in individual feature modules — import only what you need.
"""

from app.db.base import Base  # noqa: F401

# Import all models so their tables are registered with Base.metadata.
# Order: models with no FK dependencies first, then dependants.
from app.models.user import User  # noqa: F401
from app.models.team import Team, TeamMember  # noqa: F401
from app.models.social_account import (  # noqa: F401
    SocialAccount,
    AccountPermission,
    AccountSyncLog,
)
from app.models.user_settings import UserSettings  # noqa: F401
from app.models.recurring_rule import RecurringRule, RecurringRuleSocialAccount  # noqa: F401
from app.models.post import Post, PostSocialAccount  # noqa: F401
from app.models.post_publish_result import PostPublishResult  # noqa: F401


