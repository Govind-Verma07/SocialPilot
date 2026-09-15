"""
app/schemas/media.py
--------------------
Pydantic schemas for MongoDB Unified Content & Media Storage layer.
Covers:
  - MediaAssetOut / MediaUploadResponse
  - MediaItemPayload / MediaItemOut (explicit ordering for carousel & multi-asset posts)
  - PlatformOverrides & ContentPostMetadata
  - ContentPostOut & PostContentResponse
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MediaItemPayload(BaseModel):
    """Media item with explicit position ordering."""
    model_config = ConfigDict(extra="ignore")

    media_id: str = Field(..., description="Unique media UUID")
    position: int = Field(1, ge=1, description="Explicit 1-based order in carousel or sequence")


class MediaItemOut(BaseModel):
    """Populated media item with detailed asset metadata."""
    model_config = ConfigDict(extra="ignore")

    media_id: str
    position: int
    media_type: str
    original_filename: str
    mime_type: str
    size_bytes: int
    download_url: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None


class MediaAssetOut(BaseModel):
    """Metadata response for an uploaded media asset."""
    model_config = ConfigDict(extra="ignore")

    media_id: str
    user_id: str
    post_id: Optional[str] = None
    media_type: str  # "image" | "video" | "document"
    usage_type: str  # "single" | "carousel" | "story" | "reel" | "video"
    original_filename: str
    stored_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    checksum: str
    download_url: str
    public_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PlatformOverrides(BaseModel):
    """Platform-specific content & metadata overrides."""
    model_config = ConfigDict(extra="ignore")

    facebook: Optional[Dict[str, Any]] = Field(default_factory=dict)
    instagram: Optional[Dict[str, Any]] = Field(default_factory=dict)
    linkedin: Optional[Dict[str, Any]] = Field(default_factory=dict)
    x: Optional[Dict[str, Any]] = Field(default_factory=dict)
    youtube: Optional[Dict[str, Any]] = Field(default_factory=dict)
    pinterest: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ContentPostMetadata(BaseModel):
    """Metadata container for unified content post documents."""
    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    description: Optional[str] = None
    alt_text: Optional[str] = None
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    platform_overrides: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ContentPostOut(BaseModel):
    """Unified content post schema matching the content_posts MongoDB collection."""
    model_config = ConfigDict(extra="ignore")

    post_id: str
    user_id: str
    post_type: str  # "text" | "image" | "video" | "carousel" | "story" | "reel"
    text: Optional[str] = None
    media_ids: List[str] = Field(default_factory=list)
    media_items: List[MediaItemPayload] = Field(default_factory=list)
    metadata: ContentPostMetadata = Field(default_factory=ContentPostMetadata)
    status: str
    created_at: datetime
    updated_at: datetime


class PostContentDetailResponse(BaseModel):
    """Full detail response combining PostgreSQL post status with populated MongoDB media assets."""
    model_config = ConfigDict(extra="ignore")

    post_id: str
    user_id: str
    post_type: str
    text: Optional[str] = None
    media_ids: List[str] = Field(default_factory=list)
    media_items: List[MediaItemOut] = Field(default_factory=list)
    metadata: ContentPostMetadata = Field(default_factory=ContentPostMetadata)
    status: str
    created_at: datetime
    updated_at: datetime
