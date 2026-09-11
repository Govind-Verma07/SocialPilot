"""
app/services/social_metadata_service.py
---------------------------------------
Service layer for storing and retrieving rich platform-specific metadata in MongoDB.
Isolates MongoDB document operations from the PostgreSQL relational core.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from app.db.mongodb import get_mongo_db, get_social_metadata_collection

logger = logging.getLogger("uvicorn.error")


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
        await col.update_one(
            {"social_account_id": social_account_id},
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception as exc:
        logger.warning(f"Failed to save social metadata in MongoDB: {exc}")
        return False


import asyncio


async def get_social_metadata(social_account_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve platform metadata document from MongoDB for a social account."""
    db = get_mongo_db()
    if db is None:
        return None

    try:
        col = get_social_metadata_collection(db)
        doc = await asyncio.wait_for(
            col.find_one({"social_account_id": social_account_id}),
            timeout=1.5,
        )
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception as exc:
        logger.warning(f"Failed to read social metadata from MongoDB: {exc}")
        return None


async def get_social_metadata_batch(social_account_ids: list[str]) -> Dict[str, Dict[str, Any]]:
    """
    Retrieve platform metadata documents for multiple social accounts in a single MongoDB query.
    Returns a dictionary mapping social_account_id -> metadata document.
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
            timeout=2.0,
        )
        result: Dict[str, Dict[str, Any]] = {}
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
            acc_id = doc.get("social_account_id")
            if acc_id:
                result[acc_id] = doc
        return result
    except Exception as exc:
        logger.warning(f"Failed to batch read social metadata from MongoDB: {exc}")
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
