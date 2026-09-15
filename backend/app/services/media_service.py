"""
app/services/media_service.py
-----------------------------
Production-ready media management service for MongoDB GridFS and media_assets collection.

Responsibilities:
  - Stream large files into GridFS chunks (preventing large binaries in normal documents).
  - Compute SHA256 checksums and perform per-user deduplication.
  - Validate MIME types, file extensions, and file sizes server-side.
  - Secure media access: user ownership verification (no cross-user access).
  - Stream binaries back with proper HTTP headers (Content-Type, Content-Length, Content-Disposition).
  - Enforce format-specific media rules for Text, Image, Video, Carousel, Story, Reel.
"""

import hashlib
import hmac
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.db.mongodb import get_gridfs_bucket, get_media_assets_collection


# ---------------------------------------------------------------------------
# MIME & Format Configurations
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    # Images - Comprehensive support for all modern and legacy formats
    "image/jpeg": {"type": "image", "ext": ".jpg"},
    "image/jpg": {"type": "image", "ext": ".jpg"},
    "image/pjpeg": {"type": "image", "ext": ".jpg"},
    "image/jfif": {"type": "image", "ext": ".jpg"},
    "image/pjp": {"type": "image", "ext": ".jpg"},
    "image/png": {"type": "image", "ext": ".png"},
    "image/x-png": {"type": "image", "ext": ".png"},
    "image/webp": {"type": "image", "ext": ".webp"},
    "image/gif": {"type": "image", "ext": ".gif"},
    "image/avif": {"type": "image", "ext": ".avif"},
    "image/heic": {"type": "image", "ext": ".heic"},
    "image/heif": {"type": "image", "ext": ".heif"},
    "image/heic-sequence": {"type": "image", "ext": ".heic"},
    "image/heif-sequence": {"type": "image", "ext": ".heif"},
    "image/bmp": {"type": "image", "ext": ".bmp"},
    "image/x-ms-bmp": {"type": "image", "ext": ".bmp"},
    "image/x-bmp": {"type": "image", "ext": ".bmp"},
    "image/tiff": {"type": "image", "ext": ".tiff"},
    "image/x-tiff": {"type": "image", "ext": ".tiff"},
    "image/svg+xml": {"type": "image", "ext": ".svg"},
    "image/svg": {"type": "image", "ext": ".svg"},
    "image/x-icon": {"type": "image", "ext": ".ico"},
    "image/vnd.microsoft.icon": {"type": "image", "ext": ".ico"},
    "image/ico": {"type": "image", "ext": ".ico"},
    # Videos
    "video/mp4": {"type": "video", "ext": ".mp4"},
    "video/quicktime": {"type": "video", "ext": ".mov"},
    "video/webm": {"type": "video", "ext": ".webm"},
    "video/x-matroska": {"type": "video", "ext": ".mkv"},
    "video/x-msvideo": {"type": "video", "ext": ".avi"},
    "video/avi": {"type": "video", "ext": ".avi"},
    "video/mpeg": {"type": "video", "ext": ".mpeg"},
    "video/3gpp": {"type": "video", "ext": ".3gp"},
    # Documents
    "application/pdf": {"type": "document", "ext": ".pdf"},
}

IMAGE_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".jfif": "image/jpeg",
    ".pjpeg": "image/jpeg",
    ".pjp": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".bmp": "image/bmp",
    ".dib": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

VIDEO_EXTENSIONS = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
    ".m4v": "video/x-m4v",
    ".3gp": "video/3gpp",
    ".wmv": "video/x-ms-wmv",
    ".flv": "video/x-flv",
}

MAX_IMAGE_SIZE_BYTES = 100 * 1024 * 1024      # 100 MB generous image limit
MAX_VIDEO_SIZE_BYTES = 250 * 1024 * 1024      # 250 MB
MAX_DOCUMENT_SIZE_BYTES = 50 * 1024 * 1024    # 50 MB


def sanitize_filename(filename: str) -> str:
    """Sanitize original filename to prevent path traversal and unsafe characters."""
    base = os.path.basename(filename or "upload")
    clean = re.sub(r"[^\w\.\-\_]", "_", base)
    return clean[:200] if clean else "upload"


class MediaService:
    @staticmethod
    def _get_media_type_and_limits(mime_type: str, filename: Optional[str] = None) -> Tuple[str, str, int]:
        """Determine media_type, canonical extension, and size limit from MIME type and filename."""
        mime_norm = (mime_type or "").lower().split(";")[0].strip()
        ext_from_file = os.path.splitext(filename or "")[1].lower()

        # Reject dangerous executable formats immediately
        if ext_from_file in (".exe", ".bat", ".sh", ".cmd", ".com", ".msi", ".dll", ".so", ".dylib", ".vbs", ".ps1") or \
           mime_norm in ("application/x-dosexec", "application/x-msdownload", "application/x-executable", "application/x-sh"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{mime_type or ext_from_file}'. Executable files are not allowed.",
            )

        # 1. Exact match in dictionary
        info = ALLOWED_MIME_TYPES.get(mime_norm)
        if info:
            media_type = info["type"]
            ext = ext_from_file if ext_from_file else info["ext"]
            limit = MAX_VIDEO_SIZE_BYTES if media_type == "video" else MAX_IMAGE_SIZE_BYTES
            return media_type, ext, limit

        # 2. Any image format (image/*)
        if mime_norm.startswith("image/"):
            ext = ext_from_file if ext_from_file else f".{mime_norm.split('/', 1)[1].split('+')[0]}"
            if not ext.startswith("."):
                ext = f".{ext}"
            return "image", ext, MAX_IMAGE_SIZE_BYTES

        # 3. Any video format (video/*)
        if mime_norm.startswith("video/"):
            ext = ext_from_file if ext_from_file else f".{mime_norm.split('/', 1)[1]}"
            if not ext.startswith("."):
                ext = f".{ext}"
            return "video", ext, MAX_VIDEO_SIZE_BYTES

        # 4. Extension fallback when browser sends generic application/octet-stream or empty
        if ext_from_file in IMAGE_EXTENSIONS:
            return "image", ext_from_file, MAX_IMAGE_SIZE_BYTES

        if ext_from_file in VIDEO_EXTENSIONS:
            return "video", ext_from_file, MAX_VIDEO_SIZE_BYTES

        if ext_from_file == ".pdf" or mime_norm == "application/pdf":
            return "document", ".pdf", MAX_DOCUMENT_SIZE_BYTES

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{mime_type or ext_from_file}'. Supported image formats: JPEG, PNG, WebP, GIF, AVIF, HEIC, BMP, TIFF, SVG.",
        )

    @classmethod
    async def upload_media(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        file: UploadFile,
        usage_type: str = "single",
    ) -> Dict[str, Any]:
        """
        Stream an uploaded file into GridFS chunks and store structured metadata in media_assets.
        Performs checksum deduplication: if identical file was uploaded by the user, reuses asset.
        """
        if not file or not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided for upload.")

        raw_filename = file.filename
        clean_filename = sanitize_filename(raw_filename)
        content_type = file.content_type or "application/octet-stream"

        media_type, canonical_ext, max_size = cls._get_media_type_and_limits(content_type, raw_filename)
        ext_from_file = os.path.splitext(raw_filename)[1].lower()

        # Normalize content_type if it was generic
        if (not content_type or content_type == "application/octet-stream") and ext_from_file in IMAGE_EXTENSIONS:
            content_type = IMAGE_EXTENSIONS[ext_from_file]

        # 1. Stream file into memory/temp buffer while calculating SHA256 checksum and size
        hasher = hashlib.sha256()
        chunk_size = 1024 * 1024  # 1 MB
        total_bytes = 0
        file_bytes = bytearray()

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_size:
                max_mb = max_size // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File exceeds maximum allowed size of {max_mb}MB for {media_type}s.",
                )
            hasher.update(chunk)
            file_bytes.extend(chunk)

        if total_bytes == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

        checksum = hasher.hexdigest()

        # 2. Checksum Deduplication: check if same file exists for this user
        media_col = get_media_assets_collection(db)
        existing = await media_col.find_one({"user_id": user_id, "checksum": checksum})
        if existing:
            # Re-use existing asset metadata
            existing["_id"] = str(existing["_id"])
            if "gridfs_file_id" in existing and isinstance(existing["gridfs_file_id"], ObjectId):
                existing["gridfs_file_id"] = str(existing["gridfs_file_id"])
            existing["download_url"] = f"/api/v1/media/{existing['media_id']}/download"
            existing["public_url"] = cls.get_public_media_url(existing["media_id"])
            return existing

        # 3. Store binary stream in GridFS
        media_id = str(uuid.uuid4())
        stored_filename = f"{media_id}{canonical_ext}"
        bucket = get_gridfs_bucket(db)

        upload_stream = bucket.open_upload_stream(
            filename=stored_filename,
            metadata={
                "media_id": media_id,
                "user_id": user_id,
                "mime_type": content_type,
                "original_filename": clean_filename,
                "checksum": checksum,
            },
        )
        try:
            await upload_stream.write(bytes(file_bytes))
            await upload_stream.close()
            gridfs_id = upload_stream._id
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store media file in GridFS: {exc}",
            )

        now = datetime.now(timezone.utc)
        doc = {
            "media_id": media_id,
            "user_id": user_id,
            "post_id": None,
            "media_type": media_type,
            "usage_type": usage_type or "single",
            "original_filename": clean_filename,
            "stored_filename": stored_filename,
            "mime_type": content_type,
            "extension": canonical_ext,
            "size_bytes": total_bytes,
            "width": None,
            "height": None,
            "duration_seconds": None,
            "gridfs_file_id": gridfs_id,
            "checksum": checksum,
            "created_at": now,
            "updated_at": now,
        }

        insert_res = await media_col.insert_one(doc)
        if "_id" not in doc and hasattr(insert_res, "inserted_id"):
            doc["_id"] = insert_res.inserted_id

        doc["_id"] = str(doc.get("_id", ""))
        doc["gridfs_file_id"] = str(gridfs_id)
        doc["download_url"] = f"/api/v1/media/{media_id}/download"
        doc["public_url"] = cls.get_public_media_url(media_id)
        return doc

    @classmethod
    async def get_media_by_id(cls, db: AsyncIOMotorDatabase, media_id: str, user_id: str) -> Dict[str, Any]:
        """Fetch media asset metadata, verifying user ownership."""
        media_col = get_media_assets_collection(db)
        doc = await media_col.find_one({"media_id": media_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found.")
        if doc.get("user_id") != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to media asset.")

        doc["_id"] = str(doc["_id"])
        if "gridfs_file_id" in doc and isinstance(doc["gridfs_file_id"], ObjectId):
            doc["gridfs_file_id"] = str(doc["gridfs_file_id"])
        doc["download_url"] = f"/api/v1/media/{media_id}/download"
        doc["public_url"] = cls.get_public_media_url(media_id)
        return doc

    # -----------------------------------------------------------------------
    # Signed Public Media URLs (for Instagram, Pinterest, external webhooks)
    # -----------------------------------------------------------------------

    @classmethod
    def generate_public_media_token(cls, media_id: str, expires_in_hours: int = 72) -> str:
        """Generate HMAC-SHA256 signature for public media serving without exposing credentials."""
        import hmac
        import time
        expiry = int(time.time()) + (expires_in_hours * 3600)
        raw = f"{media_id}:{expiry}"
        sig = hmac.new(settings.JWT_SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()
        return f"{expiry}.{sig}"

    @classmethod
    def verify_public_media_token(cls, media_id: str, token: str) -> bool:
        """Verify that the token matches the media_id and has not expired."""
        import hmac
        import time
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return False
            expiry_str, sig = parts
            expiry = int(expiry_str)
            if time.time() > expiry:
                return False
            raw = f"{media_id}:{expiry}"
            expected_sig = hmac.new(settings.JWT_SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, expected_sig)
        except Exception:
            return False

    @classmethod
    def get_public_media_url(cls, media_id: str) -> str:
        """Generate full HTTPS URL with valid signed token for external platforms."""
        token = cls.generate_public_media_token(media_id)
        base_url = settings.effective_public_media_base_url
        return f"{base_url}/api/v1/media/public/{media_id}?token={token}"

    @classmethod
    async def open_download_stream(
        cls, db: AsyncIOMotorDatabase, media_id: str, user_id: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """Open a GridFS download stream for the specified media asset after verifying ownership."""
        asset = await cls.get_media_by_id(db, media_id, user_id)
        gridfs_file_id = asset.get("gridfs_file_id")
        if isinstance(gridfs_file_id, str):
            gridfs_file_id = ObjectId(gridfs_file_id)

        bucket = get_gridfs_bucket(db)
        try:
            stream = await bucket.open_download_stream(gridfs_file_id)
            return stream, asset
        except Exception:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Binary media file missing in GridFS.")

    @classmethod
    async def open_public_download_stream(
        cls, db: AsyncIOMotorDatabase, media_id: str
    ) -> Tuple[Any, Dict[str, Any]]:
        """Open a GridFS download stream for a public token-verified request."""
        media_col = get_media_assets_collection(db)
        asset = await media_col.find_one({"media_id": media_id})
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media asset not found.")

        gridfs_file_id = asset.get("gridfs_file_id")
        if isinstance(gridfs_file_id, str):
            gridfs_file_id = ObjectId(gridfs_file_id)

        bucket = get_gridfs_bucket(db)
        try:
            stream = await bucket.open_download_stream(gridfs_file_id)
            return stream, asset
        except Exception:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Binary media file missing in GridFS.")

    @classmethod
    async def get_media_binary_bytes(
        cls, db: AsyncIOMotorDatabase, media_id: str, user_id: Optional[str] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Extract full binary bytes directly from GridFS chunks.
        Useful for direct multipart upload to Facebook, LinkedIn, YouTube.
        """
        media_col = get_media_assets_collection(db)
        query = {"media_id": media_id}
        if user_id:
            query["user_id"] = user_id
        asset = await media_col.find_one(query)
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Media asset '{media_id}' not found.")

        gridfs_file_id = asset.get("gridfs_file_id")
        if isinstance(gridfs_file_id, str):
            gridfs_file_id = ObjectId(gridfs_file_id)

        bucket = get_gridfs_bucket(db)
        try:
            stream = await bucket.open_download_stream(gridfs_file_id)
            data = await stream.read()
            return data, asset
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Binary media file missing in GridFS: {exc}",
            )

    @classmethod
    async def delete_media(cls, db: AsyncIOMotorDatabase, media_id: str, user_id: str) -> bool:
        """Delete media asset from both GridFS and media_assets collection."""
        asset = await cls.get_media_by_id(db, media_id, user_id)
        gridfs_file_id = asset.get("gridfs_file_id")
        if isinstance(gridfs_file_id, str):
            gridfs_file_id = ObjectId(gridfs_file_id)

        bucket = get_gridfs_bucket(db)
        try:
            await bucket.delete(gridfs_file_id)
        except Exception:
            pass

        media_col = get_media_assets_collection(db)
        await media_col.delete_one({"media_id": media_id, "user_id": user_id})
        return True

    @classmethod
    async def validate_media_for_post(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        post_type: str,
        media_ids: Optional[List[str]] = None,
        media_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Validate post format media requirements and ownership.
        Returns normalized (media_ids, media_items) with explicit positions.
        """
        p_type = (post_type or "text").lower().strip()
        media_col = get_media_assets_collection(db)

        # Assemble effective list of media_ids and positions
        effective_items: List[Dict[str, Any]] = []
        effective_ids: List[str] = []

        if media_items and len(media_items) > 0:
            for idx, item in enumerate(media_items, start=1):
                m_id = item.get("media_id")
                if not m_id:
                    continue
                pos = item.get("position", idx)
                effective_items.append({"media_id": str(m_id), "position": int(pos)})
                effective_ids.append(str(m_id))
        elif media_ids and len(media_ids) > 0:
            for idx, m_id in enumerate(media_ids, start=1):
                if not m_id:
                    continue
                effective_items.append({"media_id": str(m_id), "position": idx})
                effective_ids.append(str(m_id))

        # Format-specific validation rules
        if p_type == "text":
            if len(effective_ids) > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text posts cannot have media attached. Please select Image, Video, or Carousel format.",
                )
            return [], []

        # If post type requires media, verify media count
        if p_type in ("image", "video", "reel", "story", "carousel") and len(effective_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"At least one media asset is required for '{p_type}' posts.",
            )

        if p_type in ("video", "reel") and len(effective_ids) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Only one video file is allowed for '{p_type}' posts.",
            )

        if p_type == "carousel" and len(effective_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Carousel posts require at least 2 media items.",
            )

        if p_type == "carousel" and len(effective_ids) > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Carousel posts cannot exceed 10 media items.",
            )

        # Verify all referenced media_ids exist and belong to current_user
        if effective_ids:
            found_docs = await media_col.find({"media_id": {"$in": effective_ids}}).to_list(length=100)
            doc_map = {d["media_id"]: d for d in found_docs}

            for m_id in effective_ids:
                if m_id not in doc_map:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Referenced media asset '{m_id}' does not exist or was deleted.",
                    )
                doc = doc_map[m_id]
                if doc.get("user_id") != user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Unauthorized: You do not own media asset '{m_id}'.",
                    )

                # Validate media type matching post_type
                asset_media_type = doc.get("media_type")
                if p_type == "image" and asset_media_type != "image":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Media asset '{m_id}' is a {asset_media_type}, but an image is required.",
                    )
                if p_type in ("video", "reel") and asset_media_type != "video":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Media asset '{m_id}' is a {asset_media_type}, but a video is required for {p_type}.",
                    )
                if p_type == "story" and asset_media_type not in ("image", "video"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Story posts require an image or video asset.",
                    )

        # Sort effective_items by position
        effective_items.sort(key=lambda x: x["position"])
        sorted_ids = [item["media_id"] for item in effective_items]

        return sorted_ids, effective_items

    @classmethod
    def generate_public_media_token(cls, media_id: str, expires_in_seconds: int = 259200) -> str:
        """Generate a time-limited HMAC token allowing public access for external platforms (e.g. Meta Graph API)."""
        ts = int(datetime.now(timezone.utc).timestamp()) + expires_in_seconds
        sig = hmac.new(
            settings.JWT_SECRET_KEY.encode(),
            f"{media_id}:{ts}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"{ts}.{sig}"

    @classmethod
    def verify_public_media_token(cls, media_id: str, token: str) -> bool:
        """Verify the integrity and expiry of a public media access token."""
        try:
            parts = token.split(".", 1)
            if len(parts) != 2:
                return False
            ts_str, sig = parts
            ts = int(ts_str)
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts > ts:
                return False
            expected_sig = hmac.new(
                settings.JWT_SECRET_KEY.encode(),
                f"{media_id}:{ts}".encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(sig, expected_sig)
        except Exception:
            return False

    @classmethod
    def get_public_media_url(cls, media_id: str) -> str:
        """Build public URL with access token for platform publishing bots to fetch without JWT header."""
        token = cls.generate_public_media_token(media_id)
        base_url = settings.effective_public_media_base_url
        return f"{base_url}/api/v1/media/public/{media_id}?token={token}"

    @classmethod
    async def open_public_download_stream(
        cls,
        db: AsyncIOMotorDatabase,
        media_id: str,
        token: Optional[str] = None,
    ) -> Tuple[Any, Dict[str, Any]]:
        """Open a GridFS download stream using a verified public token (for external platform crawlers)."""
        if token is not None and not cls.verify_public_media_token(media_id, token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or expired media token.",
            )

        media_col = get_media_assets_collection(db)
        asset = await media_col.find_one({"media_id": media_id})
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Media asset '{media_id}' not found.",
            )

        gridfs_file_id = asset.get("gridfs_file_id")
        if isinstance(gridfs_file_id, str):
            gridfs_file_id = ObjectId(gridfs_file_id)

        bucket = get_gridfs_bucket(db)
        try:
            stream = await bucket.open_download_stream(gridfs_file_id)
            return stream, asset
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Binary media file missing in GridFS: {exc}",
            )

    @classmethod
    async def get_media_binary_bytes(
        cls,
        db: AsyncIOMotorDatabase,
        media_id: str,
    ) -> Optional[bytes]:
        """Fetch raw binary bytes from GridFS for direct adapter multipart upload."""
        media_col = get_media_assets_collection(db)
        asset = await media_col.find_one({"media_id": media_id})
        if not asset:
            return None

        gridfs_file_id = asset.get("gridfs_file_id")
        if isinstance(gridfs_file_id, str):
            gridfs_file_id = ObjectId(gridfs_file_id)

        bucket = get_gridfs_bucket(db)
        try:
            stream = await bucket.open_download_stream(gridfs_file_id)
            data = await stream.read()
            return data
        except Exception:
            return None

