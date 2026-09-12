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
import time
from typing import Optional
# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

# Configure dnspython nameservers if available to avoid SRV resolution timeouts on local networks
try:
    import dns.resolver
    _res = dns.resolver.Resolver(configure=True)
    if "8.8.8.8" not in _res.nameservers:
        _res.nameservers = ["8.8.8.8", "1.1.1.1"] + list(_res.nameservers)
    dns.resolver.default_resolver = _res
except Exception:
    pass

# ---------------------------------------------------------------------------
# Module-level client & circuit-breaker state
# ---------------------------------------------------------------------------
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_cooldown_until: float = 0.0


def record_mongo_failure(cooldown_seconds: float = 60.0) -> None:
    """Trip the circuit breaker on failure to avoid stalling requests."""
    global _mongo_cooldown_until
    _mongo_cooldown_until = time.time() + cooldown_seconds


def record_mongo_success() -> None:
    """Reset the circuit breaker on success."""
    global _mongo_cooldown_until
    _mongo_cooldown_until = 0.0


def is_mongo_available() -> bool:
    """Check whether MongoDB client exists and is not currently in cooldown."""
    return _mongo_client is not None and time.time() >= _mongo_cooldown_until


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
            serverSelectionTimeoutMS=800,
            connectTimeoutMS=800,
            socketTimeoutMS=800,
        )
        logger.info("✅ MongoDB client initialised.")
    except Exception as exc:
        logger.warning(f"⚠️  Failed to create MongoDB client: {exc}")
        record_mongo_failure(120.0)


def disconnect_mongodb() -> None:
    """Close the Motor client. Called from main.py shutdown event."""
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        logger.info("🔌 MongoDB client closed.")


def get_mongo_db() -> Optional[AsyncIOMotorDatabase]:
    """
    Return the Motor database handle, or None if MongoDB is not configured or in cooldown.
    """
    if not is_mongo_available():
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
