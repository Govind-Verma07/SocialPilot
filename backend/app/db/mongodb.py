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
from typing import Optional, Any
# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

# Configure dnspython nameservers if available to avoid SRV resolution timeouts on local networks
try:
    import dns.resolver
    _res = dns.resolver.Resolver(configure=False)
    _res.nameservers = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]
    dns.resolver.default_resolver = _res
except Exception:
    pass

# ---------------------------------------------------------------------------
# Module-level client & circuit-breaker state
# ---------------------------------------------------------------------------
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_cooldown_until: float = 0.0
_override_mongo_db: Optional[Any] = None


def set_test_mongo_db(db: Optional[Any]) -> None:
    """Explicitly inject an in-memory or mock MongoDB database for testing."""
    global _override_mongo_db
    _override_mongo_db = db


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
    if _override_mongo_db is not None:
        return True
    return _mongo_client is not None and time.time() >= _mongo_cooldown_until


def connect_mongodb() -> None:
    """
    Create the Motor client and store it as a module-level singleton.
    Called from main.py startup event.
    """
    global _mongo_client
    if not settings.mongodb_configured:
        logger.warning(
            "⚠️  MongoDB URI is not set — MongoDB features are disabled. "
            "Add MONGODB_URI or MONGODB_URL to .env to enable document & media storage."
        )
        return

    try:
        motor_kwargs = {
            "serverSelectionTimeoutMS": 10000,
            "connectTimeoutMS": 10000,
            "socketTimeoutMS": 10000,
        }
        try:
            import certifi
            motor_kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass

        _mongo_client = AsyncIOMotorClient(
            settings.effective_mongodb_uri,
            **motor_kwargs,
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
    if _override_mongo_db is not None:
        return _override_mongo_db
    if not is_mongo_available():
        return None
    return _mongo_client[settings.effective_mongodb_database]


# ---------------------------------------------------------------------------
# GridFS & Collection accessors (Unified Content & Media Layer)
# ---------------------------------------------------------------------------

def get_gridfs_bucket(db: Any):
    """Return AsyncIOMotorGridFSBucket for binary media storage in MongoDB GridFS."""
    if hasattr(db, "_gridfs_bucket"):
        return db._gridfs_bucket
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    return AsyncIOMotorGridFSBucket(db, bucket_name="media_files")


def get_content_posts_collection(db: AsyncIOMotorDatabase):
    """
    Unified content document collection.
    Stores post_id, user_id, post_type, text, media_ids, media_items, metadata.
    """
    return db["content_posts"]


def get_media_assets_collection(db: AsyncIOMotorDatabase):
    """
    Media metadata collection.
    Stores media_id, user_id, post_id, media_type, usage_type, mime_type,
    size_bytes, gridfs_file_id, checksum, etc.
    """
    return db["media_assets"]


def get_social_metadata_collection(db: AsyncIOMotorDatabase):
    """Platform-specific metadata for connected social accounts."""
    return db["social_account_metadata"]


async def init_mongodb_indexes(db: AsyncIOMotorDatabase) -> None:
    """Initialize necessary indexes on MongoDB collections for fast lookup and uniqueness."""
    try:
        # content_posts indexes
        content_posts = get_content_posts_collection(db)
        await content_posts.create_index("post_id", unique=True)
        await content_posts.create_index("user_id")

        # media_assets indexes
        media_assets = get_media_assets_collection(db)
        await media_assets.create_index("media_id", unique=True)
        await media_assets.create_index("user_id")
        await media_assets.create_index("post_id")
        await media_assets.create_index([("user_id", 1), ("checksum", 1)])
        logger.info("✅ MongoDB indexes verified / created for content_posts and media_assets.")
    except Exception as exc:
        logger.warning(f"⚠️ Failed to create MongoDB indexes: {exc}")

