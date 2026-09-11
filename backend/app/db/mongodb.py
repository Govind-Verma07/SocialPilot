"""
app/db/mongodb.py
-----------------
MongoDB Atlas connection and async client abstraction.

Responsibilities:
  - Maintain a single Motor AsyncIOMotorClient instance.
  - Provide a `get_database()` FastAPI dependency.
  - Provide collection accessors for each Milestone-1 document type.
  - Gracefully degrade: if MONGODB_URI is not configured, all operations
    are no-ops (useful during initial dev without Atlas credentials).

Collections (Milestone 1):
  - social_account_metadata  — platform-specific rich metadata that doesn't
                               fit cleanly in the PostgreSQL relational schema
                               (e.g. profile pictures, follower counts, raw
                               platform API response fields).

Collections planned for future milestones (documented, not yet created):
  - post_drafts              — flexible draft/preview content blobs
  - campaign_briefs          — unstructured campaign notes and assets
  - analytics_snapshots      — raw platform analytics payloads
  - notification_log         — event log for push/email notifications

IMPORTANT: MongoDB is NEVER the source of truth for:
  - user identity / credentials
  - team membership
  - social account ownership / tokens
  - RBAC roles
All authoritative data lives in PostgreSQL (SQLAlchemy models).
"""

import logging
from typing import Optional
# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

# ---------------------------------------------------------------------------
# Module-level client — created once at startup
# ---------------------------------------------------------------------------
_mongo_client: Optional[AsyncIOMotorClient] = None


def connect_mongodb() -> None:
    """
    Create the Motor client and store it as a module-level singleton.
    Called from main.py startup event.
    """
    global _mongo_client
    if not settings.mongodb_configured:
        logger.warning(
            "⚠️  MONGODB_URI is not set — MongoDB features are disabled. "
            "Add MONGODB_URI to .env to enable document storage."
        )
        return

    try:
        _mongo_client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
        )
        logger.info("✅ MongoDB client initialised.")
    except Exception as exc:
        logger.warning(f"⚠️  Failed to create MongoDB client: {exc}")


def disconnect_mongodb() -> None:
    """Close the Motor client. Called from main.py shutdown event."""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        logger.info("🔌 MongoDB client closed.")


def get_mongo_db() -> Optional[AsyncIOMotorDatabase]:
    """
    Return the Motor database handle, or None if MongoDB is not configured.

    Usage in endpoint (optional dependency):
        db = Depends(get_mongo_db)
        if db is not None:
            ...
    """
    if _mongo_client is None:
        return None
    return _mongo_client[settings.MONGODB_DB_NAME]


# ---------------------------------------------------------------------------
# Collection accessors (Milestone 1)
# ---------------------------------------------------------------------------

def get_social_metadata_collection(db: AsyncIOMotorDatabase):
    """
    Platform-specific metadata for connected social accounts.

    Document shape (illustrative — schema is flexible):
    {
        "social_account_id": "<UUID from PostgreSQL social_accounts.id>",
        "platform":          "instagram",
        "profile_picture_url": "https://...",
        "follower_count":    12500,
        "following_count":   340,
        "bio":               "...",
        "raw_platform_data": { ... },   # raw API response blob
        "fetched_at":        ISODate("...")
    }

    The `social_account_id` is the FK reference to PostgreSQL.
    """
    return db["social_account_metadata"]
