"""
app/api/v1/endpoints/media.py
-----------------------------
Media upload, retrieval, download streaming, and deletion endpoints for MongoDB GridFS.

IMPORTANT: Route order matters in FastAPI.
  - Static paths (/upload, /check-tunnel, /public/{...}) MUST be registered BEFORE
    wildcard paths (/{media_id}) to prevent route shadowing.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.mongodb import get_mongo_db
from app.db.session import get_db
from app.models.user import User
from app.schemas.media import MediaAssetOut
from app.services.auth_service import get_current_user, decode_token
from app.services.media_service import MediaService

router = APIRouter()
_bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger("socialpilot.media")


# ---------------------------------------------------------------------------
# POST /upload — Upload media to GridFS
# (Static path — must come before wildcard /{media_id})
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=MediaAssetOut, status_code=status.HTTP_201_CREATED)
async def upload_media_file(
    file: UploadFile = File(...),
    usage_type: str = Form("single"),
    current_user: User = Depends(get_current_user),
) -> MediaAssetOut:
    """
    Upload an image, video, or document to MongoDB GridFS.
    Stores structured metadata in media_assets collection and returns unique media_id.
    Performs server-side MIME, size validation, and checksum deduplication.
    """
    db = get_mongo_db()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB storage is not currently available.",
        )

    doc = await MediaService.upload_media(
        db=db,
        user_id=current_user.id,
        file=file,
        usage_type=usage_type,
    )
    return MediaAssetOut(**doc)


# ---------------------------------------------------------------------------
# GET /check-tunnel — Diagnostic: verify PUBLIC_BASE_URL is reachable
# (Static path — must come before wildcard /{media_id})
# ---------------------------------------------------------------------------

@router.get("/check-tunnel", status_code=status.HTTP_200_OK)
async def check_public_url_tunnel(
    current_user: User = Depends(get_current_user),
):
    """
    Diagnostic endpoint: verifies whether the configured PUBLIC_BASE_URL is
    reachable from this server.

    Use this BEFORE publishing to Instagram or Pinterest to ensure Meta/Pinterest
    servers can fetch your media. If the tunnel is down or misconfigured, this
    will show exactly why and how to fix it.

    Returns:
        - configured_base_url: The URL from settings.effective_public_media_base_url
        - is_localhost: True if the URL points to localhost (always unreachable externally)
        - reachable: True if the URL is publicly reachable and returns valid API JSON
        - error: Human-readable error description if not reachable
        - recommendation: Step-by-step fix instructions
    """
    import httpx

    base_url = settings.effective_public_media_base_url
    is_localhost = any(h in base_url.lower() for h in ("localhost", "127.0.0.1", "0.0.0.0"))

    result = {
        "configured_base_url": base_url,
        "is_localhost": is_localhost,
        "reachable": False,
        "status_code": None,
        "content_type": None,
        "error": None,
        "recommendation": None,
    }

    if is_localhost:
        result["error"] = "PUBLIC_BASE_URL is a localhost address — external platforms like Instagram/Meta cannot reach it."
        result["recommendation"] = (
            "1. Open a terminal and start a Pinggy tunnel:\n"
            "   ssh -p 443 -R0:localhost:8000 a.pinggy.io\n"
            "2. Copy the HTTPS tunnel URL shown (e.g. https://xxxx-xx-xx-xx-xxx.run.pinggy-free.link)\n"
            "3. Update backend/.env:\n"
            "   PUBLIC_BASE_URL=https://xxxx-xx-xx-xx-xxx.run.pinggy-free.link\n"
            "   BACKEND_PUBLIC_URL=https://xxxx-xx-xx-xx-xxx.run.pinggy-free.link\n"
            "4. Restart the backend server.\n"
            "5. Call GET /api/v1/media/check-tunnel again to verify."
        )
        return JSONResponse(content=result, status_code=200)

    # Probe the root health endpoint on the public URL
    probe_url = f"{base_url}/"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8.0) as client:
            resp = await client.get(probe_url)
            content_type = resp.headers.get("content-type", "")
            result["status_code"] = resp.status_code
            result["content_type"] = content_type

            if resp.status_code == 200:
                if "text/html" in content_type:
                    # Pinggy browser-check interstitial or similar
                    result["reachable"] = False
                    result["error"] = (
                        "The tunnel URL returns an HTML page (Pinggy browser-check interstitial) "
                        "instead of API JSON. Meta/Instagram crawler bots cannot pass this interstitial check."
                    )
                    result["recommendation"] = (
                        "Restart your Pinggy tunnel with a fresh session:\n"
                        "  ssh -p 443 -R0:localhost:8000 a.pinggy.io\n"
                        "Then update PUBLIC_BASE_URL in backend/.env and restart the backend."
                    )
                else:
                    result["reachable"] = True
                    result["recommendation"] = (
                        "✅ Tunnel is reachable and returns valid API JSON. "
                        "Your backend is correctly configured for Instagram/Pinterest media delivery."
                    )
            else:
                result["error"] = f"Tunnel health check returned HTTP {resp.status_code} for {probe_url}"
                result["recommendation"] = (
                    "Verify the tunnel is running and pointing to port 8000. "
                    "Check that the backend is running with: uvicorn app.main:app --port 8000"
                )
    except httpx.ConnectError as e:
        result["error"] = f"DNS/connection failure — cannot reach {probe_url}: {e}"
        tunnel_hint = ""
        if any(h in base_url for h in ("pinggy", "ngrok", "loca.lt", "serveo")):
            tunnel_hint = (
                "\nThis looks like a tunnel URL that has expired or been closed.\n"
                "Restart it:\n"
                "  ssh -p 443 -R0:localhost:8000 a.pinggy.io\n"
                "Copy the new HTTPS URL and update PUBLIC_BASE_URL in backend/.env."
            )
        result["recommendation"] = (
            f"The configured PUBLIC_BASE_URL is unreachable.{tunnel_hint}\n"
            "After updating .env, restart the backend and call this endpoint again."
        )
    except httpx.TimeoutException:
        result["error"] = f"Connection timed out after 8 seconds probing {probe_url}"
        result["recommendation"] = (
            "Your tunnel is not responding within 8 seconds. "
            "Check that both the tunnel AND the backend server are running."
        )
    except Exception as exc:
        result["error"] = f"Unexpected error: {exc}"

    logger.info("Tunnel check result for user %s: reachable=%s url=%s", current_user.id, result["reachable"], base_url)
    return JSONResponse(content=result, status_code=200)


# ---------------------------------------------------------------------------
# GET /public/{media_id} — Public unauthenticated media stream (for Instagram/Pinterest)
# (Static prefix /public/ — must come before wildcard /{media_id})
# ---------------------------------------------------------------------------

@router.get("/public/{media_id}")
async def download_public_media_stream(
    media_id: str,
    token: str = Query(..., description="HMAC-signed access token for external platforms"),
):
    """
    Stream binary media file to external platforms (Instagram Graph API, Pinterest API)
    using a secure HMAC-signed token, without exposing user credentials or requiring JWT.

    Headers returned are optimized for Meta/Instagram crawler compatibility:
    - Content-Type: canonical MIME (image/jpeg for all JPEG variants)
    - Content-Length: exact byte count
    - Accept-Ranges: bytes (required by some Meta validators)
    - Access-Control-Allow-Origin: * (allows cross-origin crawl)
    - X-Content-Type-Options: nosniff (prevents MIME sniffing)
    - Cache-Control: public, max-age=86400 (1 day cache)
    """
    if not MediaService.verify_public_media_token(media_id, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired media token.",
        )

    db = get_mongo_db()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB storage is not currently available.",
        )

    stream, asset = await MediaService.open_public_download_stream(db, media_id)

    async def _streamer():
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            yield chunk

    mime = asset.get("mime_type", "application/octet-stream")
    # Normalize JPEG MIME variants to canonical image/jpeg (required by Meta)
    if mime in ("image/jpg", "image/pjpeg", "image/jfif", "image/pjp"):
        mime = "image/jpeg"

    headers = {
        "Content-Disposition": f'inline; filename="{asset.get("original_filename", "media")}"',
        "Content-Length": str(asset.get("size_bytes", "")),
        "Cache-Control": "public, max-age=86400",
        "Accept-Ranges": "bytes",
        "Access-Control-Allow-Origin": "*",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(_streamer(), media_type=mime, headers=headers)


# ---------------------------------------------------------------------------
# GET /{media_id}/download — Authenticated/token media stream (for frontend preview)
# ---------------------------------------------------------------------------

@router.get("/{media_id}/download")
async def download_media_stream(
    media_id: str,
    token: Optional[str] = Query(None, description="Optional access token (JWT or HMAC) for inline media previews"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db_session: Session = Depends(get_db),
):
    """
    Stream binary media file directly from MongoDB GridFS chunks.
    Ensures safe inline streaming with proper Content-Type and caching headers.
    Supports:
      1. Header: Authorization: Bearer <jwt>
      2. Query Param: ?token=<jwt> or ?token=<hmac_token>
      3. Direct preview: streams file directly by media_id for HTML <img> and <video> elements
    """
    db = get_mongo_db()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB storage is not currently available.",
        )

    if credentials:
        current_user = get_current_user(credentials, db_session)
        stream, asset = await MediaService.open_download_stream(db, media_id, current_user.id)
    elif token:
        try:
            payload = decode_token(token)
            stream, asset = await MediaService.open_download_stream(db, media_id, payload.sub)
        except Exception:
            if MediaService.verify_public_media_token(media_id, token):
                stream, asset = await MediaService.open_public_download_stream(db, media_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired media token.",
                )
    else:
        stream, asset = await MediaService.open_public_download_stream(db, media_id)

    async def _streamer():
        while True:
            chunk = await stream.readchunk()
            if not chunk:
                break
            yield chunk

    headers = {
        "Content-Disposition": f'inline; filename="{asset.get("original_filename", "media")}"',
        "Content-Length": str(asset.get("size_bytes", "")),
        "Cache-Control": "public, max-age=86400",
    }
    return StreamingResponse(_streamer(), media_type=asset.get("mime_type", "application/octet-stream"), headers=headers)


# ---------------------------------------------------------------------------
# GET /{media_id} — Fetch media metadata (authenticated)
# (Wildcard path — must come AFTER all static paths)
# ---------------------------------------------------------------------------

@router.get("/{media_id}", response_model=MediaAssetOut, status_code=status.HTTP_200_OK)
async def get_media_metadata(
    media_id: str,
    current_user: User = Depends(get_current_user),
) -> MediaAssetOut:
    """Fetch metadata for a media asset owned by the authenticated user."""
    db = get_mongo_db()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB storage is not currently available.",
        )

    doc = await MediaService.get_media_by_id(db, media_id, current_user.id)
    return MediaAssetOut(**doc)


# ---------------------------------------------------------------------------
# DELETE /{media_id} — Delete media asset (authenticated)
# ---------------------------------------------------------------------------

@router.delete("/{media_id}", status_code=status.HTTP_200_OK)
async def delete_media_file(
    media_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a media asset and its binary chunks from MongoDB GridFS."""
    db = get_mongo_db()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB storage is not currently available.",
        )

    success = await MediaService.delete_media(db, media_id, current_user.id)
    return {"success": success, "message": "Media asset deleted successfully."}
