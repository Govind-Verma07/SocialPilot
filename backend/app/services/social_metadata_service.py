"""
app/services/social_metadata_service.py
---------------------------------------
Service layer for storing and retrieving rich platform-specific metadata in MongoDB.
Isolates MongoDB document operations from the PostgreSQL relational core.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional

from app.db.mongodb import (
    get_mongo_db,
    get_social_metadata_collection,
    record_mongo_failure,
    record_mongo_success,
)

logger = logging.getLogger("uvicorn.error")

MONGO_OP_TIMEOUT_SECONDS = 0.4


async def save_social_metadata(
    social_account_id: str,
    platform: str,
    raw_metadata: Dict[str, Any],
    profile_picture_url: Optional[str] = None,
) -> bool:
    """
    Store or update flexible platform metadata document in MongoDB.
    Returns True if saved, False if MongoDB is unconfigured or unavailable.
    """
    db = get_mongo_db()
    if db is None:
        return False

    try:
        col = get_social_metadata_collection(db)
        doc = {
            "social_account_id": social_account_id,
            "platform": platform,
            "profile_picture_url": profile_picture_url,
            "raw_metadata": raw_metadata,
            "updated_at": datetime.now(timezone.utc),
        }
        await asyncio.wait_for(
            col.update_one(
                {"social_account_id": social_account_id},
                {"$set": doc},
                upsert=True,
            ),
            timeout=MONGO_OP_TIMEOUT_SECONDS,
        )
        record_mongo_success()
        return True
    except Exception as exc:
        logger.warning(f"Failed to save social metadata in MongoDB: {exc}")
        record_mongo_failure()
        return False


async def get_social_metadata(social_account_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve platform metadata document from MongoDB for a social account."""
    db = get_mongo_db()
    if db is None:
        return None

    try:
        col = get_social_metadata_collection(db)
        doc = await asyncio.wait_for(
            col.find_one({"social_account_id": social_account_id}),
            timeout=MONGO_OP_TIMEOUT_SECONDS,
        )
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        record_mongo_success()
        return doc
    except Exception as exc:
        logger.warning(f"Failed to read social metadata from MongoDB: {exc}")
        record_mongo_failure()
        return None


async def get_batch_social_metadata(social_account_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Retrieve platform metadata documents for multiple accounts in a single batch query.
    Fails fast without blocking if MongoDB is slow or unreachable.
    """
    if not social_account_ids:
        return {}

    db = get_mongo_db()
    if db is None:
        return {}

    try:
        col = get_social_metadata_collection(db)
        cursor = col.find({"social_account_id": {"$in": social_account_ids}})
        docs = await asyncio.wait_for(
            cursor.to_list(length=len(social_account_ids)),
            timeout=MONGO_OP_TIMEOUT_SECONDS,
        )
        result: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            acc_id = doc.get("social_account_id")
            if acc_id:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                result[acc_id] = doc
        record_mongo_success()
        return result
    except Exception as exc:
        logger.warning(f"Failed to read batch social metadata from MongoDB: {exc}")
        record_mongo_failure()
        return {}


async def delete_social_metadata(social_account_id: str) -> bool:
    """Clean up metadata document when an account is disconnected."""
    db = get_mongo_db()
    if db is None:
        return False

    try:
        col = get_social_metadata_collection(db)
        await col.delete_one({"social_account_id": social_account_id})
        return True
    except Exception as exc:
        logger.warning(f"Failed to delete social metadata from MongoDB: {exc}")
        return False
