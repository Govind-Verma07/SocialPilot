"""
app/services/content_post_service.py
------------------------------------
Service layer for managing unified content documents in MongoDB `content_posts` collection.
Coordinates post content, rich metadata, and media associations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_content_posts_collection, get_media_assets_collection


class ContentPostService:
    @classmethod
    async def upsert_content_post(
        cls,
        db: AsyncIOMotorDatabase,
        post_id: str,
        user_id: str,
        post_type: str,
        text: Optional[str],
        media_ids: List[str],
        media_items: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "draft",
    ) -> Dict[str, Any]:
        """
        Create or update a unified content document in MongoDB `content_posts`.
        Also links referenced media_assets to this post_id.
        """
        content_col = get_content_posts_collection(db)
        media_col = get_media_assets_collection(db)
        now = datetime.now(timezone.utc)

        clean_metadata = metadata or {}
        if not isinstance(clean_metadata, dict):
            clean_metadata = {}

        doc = {
            "post_id": post_id,
            "user_id": user_id,
            "post_type": post_type or "text",
            "text": text,
            "media_ids": media_ids or [],
            "media_items": media_items or [],
            "metadata": {
                "title": clean_metadata.get("title"),
                "description": clean_metadata.get("description"),
                "alt_text": clean_metadata.get("alt_text"),
                "hashtags": clean_metadata.get("hashtags", []),
                "mentions": clean_metadata.get("mentions", []),
                "platform_overrides": clean_metadata.get("platform_overrides", {}),
            },
            "status": status,
            "updated_at": now,
        }

        # Check existing
        existing = await content_col.find_one({"post_id": post_id})
        if existing:
            await content_col.update_one({"post_id": post_id}, {"$set": doc})
            doc["created_at"] = existing.get("created_at", now)
        else:
            doc["created_at"] = now
            await content_col.insert_one(doc)

        # Associate referenced media assets with this post_id
        if media_ids:
            await media_col.update_many(
                {"media_id": {"$in": media_ids}, "user_id": user_id},
                {"$set": {"post_id": post_id, "updated_at": now}},
            )

        doc.pop("_id", None)
        return doc

    @classmethod
    async def get_content_post(
        cls, db: AsyncIOMotorDatabase, post_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a unified content document and populate detailed media asset metadata.
        """
        content_col = get_content_posts_collection(db)
        media_col = get_media_assets_collection(db)

        query: Dict[str, Any] = {"post_id": post_id}
        if user_id:
            query["user_id"] = user_id

        doc = await content_col.find_one(query)
        if not doc:
            return None

        doc.pop("_id", None)

        # Populate media_items with full media asset metadata
        media_ids = doc.get("media_ids", [])
        if media_ids:
            assets = await media_col.find({"media_id": {"$in": media_ids}}).to_list(length=100)
            asset_map = {a["media_id"]: a for a in assets}

            populated_items = []
            for item in doc.get("media_items", []):
                m_id = item.get("media_id")
                pos = item.get("position", 1)
                asset = asset_map.get(m_id)
                if asset:
                    populated_items.append({
                        "media_id": m_id,
                        "position": pos,
                        "media_type": asset.get("media_type", "image"),
                        "original_filename": asset.get("original_filename", ""),
                        "mime_type": asset.get("mime_type", ""),
                        "size_bytes": asset.get("size_bytes", 0),
                        "download_url": f"/api/v1/media/{m_id}/download",
                        "width": asset.get("width"),
                        "height": asset.get("height"),
                        "duration_seconds": asset.get("duration_seconds"),
                    })
                else:
                    populated_items.append({
                        "media_id": m_id,
                        "position": pos,
                        "media_type": "unknown",
                        "original_filename": "missing_asset",
                        "mime_type": "",
                        "size_bytes": 0,
                        "download_url": f"/api/v1/media/{m_id}/download",
                    })
            doc["media_items"] = populated_items

        return doc

    @classmethod
    async def delete_content_post(cls, db: AsyncIOMotorDatabase, post_id: str, user_id: str) -> bool:
        """Delete content post document and disassociate media assets."""
        content_col = get_content_posts_collection(db)
        media_col = get_media_assets_collection(db)

        res = await content_col.delete_one({"post_id": post_id, "user_id": user_id})
        if res.deleted_count > 0:
            # Unlink post_id from media assets
            await media_col.update_many(
                {"post_id": post_id, "user_id": user_id},
                {"$set": {"post_id": None, "updated_at": datetime.now(timezone.utc)}},
            )
            return True
        return False
