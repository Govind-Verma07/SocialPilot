"""
app/services/publishing/media_resolver.py
-----------------------------------------
Common Media Resolution Service for SocialPilot Multi-Platform Publishing Pipeline.
Resolves rich media assets from MongoDB content_posts, media_assets, and GridFS
prior to invoking platform adapters, providing a unified, normalized context.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.post import Post
from app.db.mongodb import get_mongo_db, get_content_posts_collection, get_media_assets_collection
from app.services.media_service import MediaService

logger = logging.getLogger("socialpilot.publishing.media")


@dataclass
class ResolvedMediaItem:
    """Represents a single verified media asset with metadata and public serving URL."""
    media_id: str
    position: int
    media_type: str               # "image", "video", "document"
    usage_type: str               # "single", "carousel", "story", "reel"
    mime_type: str                # e.g. "image/jpeg", "video/mp4"
    original_filename: str
    size_bytes: int
    gridfs_file_id: Optional[str] = None
    public_url: Optional[str] = None

    @property
    def format(self) -> str:
        return self.usage_type or self.media_type

    @property
    def filename(self) -> str:
        return self.original_filename


@dataclass
class PostPublishContext:
    """
    Standardized, format-agnostic publishing context passed to all platform adapters.
    Guarantees that media counts, ordered items, and public URLs are never lost.
    """
    post: Post
    post_id: str
    user_id: str
    post_type: str                # "text", "image", "video", "carousel", "story", "reel"
    content: str
    media_items: List[ResolvedMediaItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_media(self) -> bool:
        return len(self.media_items) > 0

    @property
    def media_count(self) -> int:
        return len(self.media_items)

    @property
    def primary_media(self) -> Optional[ResolvedMediaItem]:
        return self.media_items[0] if self.media_items else None

    @property
    def primary_item(self) -> Optional[ResolvedMediaItem]:
        return self.media_items[0] if self.media_items else None

    @property
    def is_video(self) -> bool:
        if self.post_type in ("video", "reel"):
            return True
        return bool(self.primary_media and self.primary_media.media_type == "video")

    @property
    def has_video(self) -> bool:
        return self.is_video

    @property
    def is_carousel(self) -> bool:
        return self.post_type == "carousel" and len(self.media_items) > 1


async def resolve_post_publish_context(db: Session, post: Post) -> PostPublishContext:
    """
    Resolve the unified PostPublishContext for a post.
    Queries MongoDB content_posts and media_assets to rebuild the complete media payload.
    Emits structured debug logs to ensure zero silent data loss.
    """
    post_id = str(post.id)
    user_id = str(post.user_id)
    effective_post_type = (post.post_type or "text").lower().strip()
    effective_content = post.content or ""

    resolved_items: List[ResolvedMediaItem] = []
    meta_dict: Dict[str, Any] = {}
    extracted_media_ids: List[str] = []

    mongo_db = get_mongo_db()

    if mongo_db is not None:
        try:
            content_col = get_content_posts_collection(mongo_db)
            content_doc = await content_col.find_one({"post_id": post_id})

            if content_doc:
                # Synchronize post_type if richer in MongoDB
                if content_doc.get("post_type"):
                    effective_post_type = str(content_doc["post_type"]).lower().strip()

                meta_dict = content_doc.get("metadata") or {}
                raw_items = content_doc.get("media_items") or []
                raw_ids = content_doc.get("media_ids") or []

                # Build ordered list of media IDs
                ordered_ids: List[tuple[str, int]] = []
                if raw_items:
                    for idx, it in enumerate(raw_items, start=1):
                        m_id = it.get("media_id")
                        if m_id:
                            pos = it.get("position", idx)
                            ordered_ids.append((str(m_id), int(pos)))
                elif raw_ids:
                    for idx, m_id in enumerate(raw_ids, start=1):
                        ordered_ids.append((str(m_id), idx))

                # Sort by position
                ordered_ids.sort(key=lambda x: x[1])
                extracted_media_ids = [m[0] for m in ordered_ids]

                if extracted_media_ids:
                    media_col = get_media_assets_collection(mongo_db)
                    cursor = media_col.find({"media_id": {"$in": extracted_media_ids}})
                    found_docs = await cursor.to_list(length=100)
                    doc_map = {d["media_id"]: d for d in found_docs}

                    for m_id, pos in ordered_ids:
                        asset = doc_map.get(m_id)
                        if asset:
                            public_url = MediaService.get_public_media_url(m_id)
                            gridfs_fid = str(asset.get("gridfs_file_id", ""))
                            resolved_items.append(
                                ResolvedMediaItem(
                                    media_id=m_id,
                                    position=pos,
                                    media_type=asset.get("media_type", "image"),
                                    usage_type=asset.get("usage_type", "single"),
                                    mime_type=asset.get("mime_type", "image/jpeg"),
                                    original_filename=asset.get("original_filename", "media"),
                                    size_bytes=asset.get("size_bytes", 0),
                                    gridfs_file_id=gridfs_fid,
                                    public_url=public_url,
                                )
                            )
                        else:
                            logger.warning(
                                "Referenced media asset '%s' not found in MongoDB for post #%s",
                                m_id,
                                post_id,
                            )
        except Exception as exc:
            logger.error("Error resolving MongoDB content_post for post #%s: %s", post_id, exc)

    # Fallback: support post.media_urls if no items resolved from MongoDB content_posts
    if not resolved_items and post.media_urls:
        import re
        for idx, url in enumerate(post.media_urls, start=1):
            url_str = str(url).strip()
            if not url_str:
                continue

            # Extract media_id from public URL if present (/api/v1/media/public/{media_id})
            m_match = re.search(r"/api/v1/media/public/([a-f0-9\-]+)", url_str)
            parsed_id = m_match.group(1) if m_match else f"media_{idx}"

            is_vid = any(url_str.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"))
            m_type = "video" if is_vid else "image"
            mime_type = "video/mp4" if is_vid else "image/jpeg"
            orig_name = f"media_{idx}"
            size_b = 0
            gridfs_fid = None

            if mongo_db is not None and m_match:
                try:
                    media_col = get_media_assets_collection(mongo_db)
                    asset = await media_col.find_one({"media_id": parsed_id})
                    if asset:
                        m_type = asset.get("media_type", m_type)
                        mime_type = asset.get("mime_type", mime_type)
                        orig_name = asset.get("original_filename", orig_name)
                        size_b = asset.get("size_bytes", 0)
                        gridfs_fid = str(asset.get("gridfs_file_id", ""))
                except Exception:
                    pass

            # If the URL is our media endpoint, always regenerate using current PUBLIC_BASE_URL
            item_public_url = MediaService.get_public_media_url(parsed_id) if m_match else url_str

            resolved_items.append(
                ResolvedMediaItem(
                    media_id=parsed_id,
                    position=idx,
                    media_type=m_type,
                    usage_type="single",
                    mime_type=mime_type,
                    original_filename=orig_name,
                    size_bytes=size_b,
                    gridfs_file_id=gridfs_fid,
                    public_url=item_public_url,
                )
            )
            extracted_media_ids.append(parsed_id)

    # Structured debug logging
    logger.info(
        "Resolved PostPublishContext: post_id=%s, post_type=%s, media_count=%d, media_ids=%s, resolved_media_count=%d, resolved_media_types=%s",
        post_id,
        effective_post_type,
        len(extracted_media_ids),
        extracted_media_ids,
        len(resolved_items),
        [item.media_type for item in resolved_items],
    )

    return PostPublishContext(
        post=post,
        post_id=post_id,
        user_id=user_id,
        post_type=effective_post_type,
        content=effective_content,
        media_items=resolved_items,
        metadata=meta_dict,
    )
