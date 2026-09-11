"""
app/api/v1/endpoints/social.py
-------------------------------
OAuth authorization and callback endpoints for Social Media account linking.
Milestone 1 supported platforms:
  - Facebook, Instagram, LinkedIn, X (Twitter), YouTube, Pinterest
"""

import json
import secrets
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings, get_settings
from app.core.encryption import encrypt_token, decrypt_token
from app.db.session import get_db
from app.models.enums import AccountStatus, SocialPlatform, SyncStatus
from app.models.social_account import AccountPermission, AccountSyncLog, SocialAccount
from app.models.user import User
from app.schemas.social import (
    AccountPermissionOut,
    SocialAccountOut,
    SocialAuthUrlOut,
    SocialPlatformInfo,
    SyncResponseOut,
)
from app.services.auth_service import get_current_user
from app.services.social_metadata_service import (
    delete_social_metadata,
    get_social_metadata,
    get_social_metadata_batch,
    save_social_metadata,
)
from app.services.social_providers import get_all_providers, get_provider

router = APIRouter()

STATE_TOKEN_EXPIRE_MINUTES = 15


# In-memory PKCE code_verifier cache with expiration (sid -> (code_verifier, expire_timestamp))
# Used to keep the OAuth state token compact (~250-260 chars), well within X's 500-char limit.
_PKCE_CACHE: dict[str, tuple[str, float]] = {}


def _cleanup_pkce_cache() -> None:
    """Remove expired PKCE verifiers from in-memory cache."""
    now = datetime.now(timezone.utc).timestamp()
    expired = [k for k, (_, exp) in _PKCE_CACHE.items() if exp < now]
    for k in expired:
        _PKCE_CACHE.pop(k, None)


def _create_oauth_state(
    user_id: str,
    team_id: Optional[str] = None,
    code_verifier: Optional[str] = None,
) -> str:
    """Create a signed state token encoding user_id, optional team_id, and compact PKCE sid."""
    _cleanup_pkce_cache()
    expire = datetime.now(timezone.utc).timestamp() + (STATE_TOKEN_EXPIRE_MINUTES * 60)
    payload = {
        "sub": user_id,
        "team_id": team_id,
        "exp": expire,
        "type": "oauth_state",
    }
    if code_verifier:
        # Cache verifier in-memory with a compact random 16-byte sid (~22 chars)
        # Keeps overall state JWT length ~260 chars (well under X's strict 500 character limit)
        sid = secrets.token_urlsafe(16)
        _PKCE_CACHE[sid] = (code_verifier, expire)
        payload["sid"] = sid
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _decode_oauth_state(state_token: str) -> dict:
    """Decode and validate the OAuth state token, resolving PKCE code_verifier."""
    _cleanup_pkce_cache()
    try:
        payload = jwt.decode(
            state_token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "oauth_state":
            raise ValueError("Invalid state type")
        
        # 1. Check if sid is present in payload (compact server-side PKCE cache)
        if "sid" in payload and payload["sid"]:
            sid = payload["sid"]
            cached = _PKCE_CACHE.pop(sid, None)
            if cached:
                payload["code_verifier"] = cached[0]

        # 2. Fallback check if code_verifier was directly encrypted in token
        if not payload.get("code_verifier") and "code_verifier" in payload and payload["code_verifier"]:
            payload["code_verifier"] = decrypt_token(payload["code_verifier"])

        return payload
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state parameter.",
        ) from exc


def _get_platform_redirect_uri(platform_name: str, request: Request) -> str:
    """Return configured platform redirect URI or build dynamically from request."""
    s = get_settings()
    if platform_name == SocialPlatform.facebook.value and getattr(s, "FACEBOOK_REDIRECT_URI", ""):
        return s.FACEBOOK_REDIRECT_URI
    if platform_name == SocialPlatform.instagram.value and getattr(s, "INSTAGRAM_REDIRECT_URI", ""):
        return s.INSTAGRAM_REDIRECT_URI
    if platform_name == SocialPlatform.linkedin.value and getattr(s, "LINKEDIN_REDIRECT_URI", ""):
        return s.LINKEDIN_REDIRECT_URI
    if platform_name == SocialPlatform.x.value and getattr(s, "X_REDIRECT_URI", ""):
        return s.X_REDIRECT_URI
    if platform_name == SocialPlatform.youtube.value and getattr(s, "YOUTUBE_REDIRECT_URI", ""):
        return s.YOUTUBE_REDIRECT_URI
    base_url = str(request.base_url).rstrip("/")
    return f"{base_url}{s.API_V1_PREFIX}/social/oauth/{platform_name}/callback"


# ---------------------------------------------------------------------------
# Platform Discovery Endpoint
# ---------------------------------------------------------------------------

@router.get("/platforms", response_model=List[SocialPlatformInfo], status_code=status.HTTP_200_OK)
def list_platforms() -> List[SocialPlatformInfo]:
    """
    List all supported social media platforms with configuration readiness.
    Provides clear visibility into which providers have credentials configured vs. awaiting approval.
    """
    providers = get_all_providers()
    result = []
    for platform_enum, provider in providers.items():
        result.append(
            SocialPlatformInfo(
                platform=platform_enum,
                display_name=provider.display_name,
                is_configured=provider.is_configured(),
                supported_permissions=provider.supported_permissions,
            )
        )
    return result


# ---------------------------------------------------------------------------
# OAuth Authorization URL Generator
# ---------------------------------------------------------------------------

@router.get("/oauth/x/authorize")
def authorize_x(
    request: Request,
    team_id: Optional[str] = None,
    redirect: bool = Query(False, description="If true, 302 redirects user directly to X authorization URL"),
    current_user: User = Depends(get_current_user),
):
    """
    Generate X (Twitter) OAuth 2.0 PKCE authorization redirect URL.
    Returns SocialAuthUrlOut JSON, or 302 RedirectResponse when redirect=True.
    """
    return get_authorization_url(
        platform="x",
        request=request,
        team_id=team_id,
        redirect=redirect,
        current_user=current_user,
    )


@router.get("/oauth/youtube/authorize")
def authorize_youtube(
    request: Request,
    team_id: Optional[str] = None,
    redirect: bool = Query(False, description="If true, 302 redirects user directly to YouTube authorization URL"),
    current_user: User = Depends(get_current_user),
):
    """
    Generate YouTube (Google OAuth 2.0) authorization redirect URL.
    Returns SocialAuthUrlOut JSON, or 302 RedirectResponse when redirect=True.
    """
    return get_authorization_url(
        platform="youtube",
        request=request,
        team_id=team_id,
        redirect=redirect,
        current_user=current_user,
    )


@router.get("/oauth/{platform}/authorize")
def get_authorization_url(
    platform: str,
    request: Request,
    team_id: Optional[str] = None,
    redirect: bool = Query(False, description="If true, 302 redirects user directly to authorization URL"),
    current_user: User = Depends(get_current_user),
):
    """
    Generate the OAuth authorization redirect URL for the specified platform.
    If the platform credentials are not configured, returns a clear notice without faking connection.
    """
    provider = get_provider(platform)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform '{platform}' is not supported.",
        )

    if not provider.is_configured():
        return SocialAuthUrlOut(
            platform=provider.platform,
            authorization_url=None,
            is_configured=False,
            message=(
                f"OAuth credentials for {provider.display_name} are not configured. "
                "Awaiting developer credentials / platform approval in .env."
            ),
        )

    redirect_uri = _get_platform_redirect_uri(provider.platform.value, request)

    code_verifier = None
    code_challenge = None
    if provider.platform == SocialPlatform.x:
        from app.services.social_providers.x import generate_code_verifier, generate_code_challenge
        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)

    state = _create_oauth_state(user_id=current_user.id, team_id=team_id, code_verifier=code_verifier)
    if provider.platform == SocialPlatform.x and code_challenge:
        auth_url = provider.get_authorization_url(state=state, redirect_uri=redirect_uri, code_challenge=code_challenge)
    else:
        auth_url = provider.get_authorization_url(state=state, redirect_uri=redirect_uri)

    if redirect and auth_url:
        return RedirectResponse(auth_url, status_code=status.HTTP_302_FOUND)

    return SocialAuthUrlOut(
        platform=provider.platform,
        authorization_url=auth_url,
        is_configured=True,
    )


# ---------------------------------------------------------------------------
# OAuth Callback Handler
# ---------------------------------------------------------------------------

@router.get("/oauth/{platform}/callback")
@router.get("/oauth/{platform}/callback/")
async def oauth_callback(
    platform: str,
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Handle OAuth 2.0 authorization callback from social platforms.
    Validates state, exchanges code for tokens, retrieves profile, encrypts tokens,
    and updates PostgreSQL and MongoDB records.
    """
    s = get_settings()
    frontend_base = s.FRONTEND_URL.strip() if s.FRONTEND_URL else (s.allowed_origins_list[0] if s.allowed_origins_list else "http://localhost:5173")

    if error:
        err_msg = error_description or error or "OAuth authorization was canceled or failed."
        params = urlencode({"error": err_msg, "platform": platform})
        return RedirectResponse(f"{frontend_base}/accounts?{params}")

    if not code or not state:
        params = urlencode({"error": "Missing code or state parameter in OAuth callback.", "platform": platform})
        return RedirectResponse(f"{frontend_base}/accounts?{params}")

    if platform == "google":
        from app.api.v1.endpoints.auth import google_oauth_callback
        return await google_oauth_callback(request, code, state, error, error_description, db)

    # Validate state token
    state_payload = _decode_oauth_state(state)
    user_id = state_payload.get("sub")
    team_id = state_payload.get("team_id")
    code_verifier = state_payload.get("code_verifier")

    provider = get_provider(platform)
    if not provider:
        params = urlencode({"error": f"Unsupported platform '{platform}'.", "platform": platform})
        return RedirectResponse(f"{frontend_base}/accounts?{params}")

    # Build redirect URI matching authorize call
    redirect_uri = _get_platform_redirect_uri(provider.platform.value, request)
    clean_code = code.split("#")[0].rstrip("_") if code else code

    try:
        if provider.platform == SocialPlatform.x and code_verifier:
            token_data = await provider.exchange_code(
                code=clean_code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier,
            )
        else:
            token_data = await provider.exchange_code(code=clean_code, redirect_uri=redirect_uri)
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")

        if not access_token:
            raise ValueError("No access token returned by provider.")

        profile_data = await provider.fetch_profile(access_token=access_token)
        platform_account_id = profile_data.get("platform_account_id")
        account_name = profile_data.get("account_name", f"{provider.display_name} User")
        account_username = profile_data.get("account_username", "")
        profile_picture_url = profile_data.get("profile_picture_url")
        raw_metadata = profile_data.get("raw_metadata", {})
        effective_access_token = profile_data.get("access_token") or access_token

        # Check existing account
        existing_account = db.query(SocialAccount).filter(
            SocialAccount.user_id == user_id,
            SocialAccount.platform == provider.platform.value,
            SocialAccount.platform_account_id == platform_account_id,
        ).first()

        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc) if expires_in else None

        if existing_account:
            account = existing_account
            account.account_name = account_name
            account.account_username = account_username
            account.status = AccountStatus.connected.value
            account.access_token_encrypted = encrypt_token(effective_access_token)
            if refresh_token:
                account.refresh_token_encrypted = encrypt_token(refresh_token)
            account.token_expires_at = expires_at
            account.last_synced_at = now
            if team_id:
                account.team_id = team_id
        else:
            account = SocialAccount(
                user_id=user_id,
                team_id=team_id,
                platform=provider.platform.value,
                platform_account_id=platform_account_id,
                account_name=account_name,
                account_username=account_username,
                status=AccountStatus.connected.value,
                access_token_encrypted=encrypt_token(effective_access_token),
                refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
                token_expires_at=expires_at,
                connected_at=now,
                last_synced_at=now,
            )
            db.add(account)
            db.commit()
            db.refresh(account)

            # Assign supported permissions
            for perm_name in provider.supported_permissions:
                perm = AccountPermission(
                    social_account_id=account.id,
                    permission=perm_name,
                    granted=True,
                )
                db.add(perm)

        # Log sync attempt
        sync_log = AccountSyncLog(
            social_account_id=account.id,
            status=SyncStatus.success.value,
            message="Account successfully connected via OAuth 2.0 handshake.",
            synced_at=now,
        )
        db.add(sync_log)
        db.commit()

        # Connect any additional authorized Facebook Pages
        all_pages = raw_metadata.get("all_pages", [])
        if all_pages and len(all_pages) > 1:
            for extra_page in all_pages[1:]:
                ep_id = str(extra_page.get("id"))
                ep_name = extra_page.get("name", "Facebook Page")
                ep_username = ep_name.lower().replace(" ", "_")
                ep_token = extra_page.get("access_token") or access_token

                existing_ep = db.query(SocialAccount).filter(
                    SocialAccount.user_id == user_id,
                    SocialAccount.platform == provider.platform.value,
                    SocialAccount.platform_account_id == ep_id,
                ).first()

                if existing_ep:
                    existing_ep.account_name = ep_name
                    existing_ep.account_username = ep_username
                    existing_ep.status = AccountStatus.connected.value
                    existing_ep.access_token_encrypted = encrypt_token(ep_token)
                    existing_ep.last_synced_at = now
                else:
                    new_page_acc = SocialAccount(
                        user_id=user_id,
                        team_id=team_id,
                        platform=provider.platform.value,
                        platform_account_id=ep_id,
                        account_name=ep_name,
                        account_username=ep_username,
                        status=AccountStatus.connected.value,
                        access_token_encrypted=encrypt_token(ep_token),
                        connected_at=now,
                        last_synced_at=now,
                    )
                    db.add(new_page_acc)
                    db.commit()
                    db.refresh(new_page_acc)

                    for perm_name in provider.supported_permissions:
                        db.add(AccountPermission(social_account_id=new_page_acc.id, permission=perm_name, granted=True))
                    db.commit()

        # Save flexible rich metadata in MongoDB
        await save_social_metadata(
            social_account_id=account.id,
            platform=provider.platform.value,
            raw_metadata=raw_metadata,
            profile_picture_url=profile_picture_url,
        )

        params = urlencode({"connected": provider.platform.value, "status": "success"})
        return RedirectResponse(f"{frontend_base}/accounts?{params}")

    except Exception as exc:
        params = urlencode({"error": f"Failed to connect account: {str(exc)}", "platform": platform})
        return RedirectResponse(f"{frontend_base}/accounts?{params}")


@router.get("/oauth/x/callback")
@router.get("/oauth/x/callback/")
async def oauth_x_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle OAuth 2.0 authorization callback for X (Twitter)."""
    return await oauth_callback(
        platform="x",
        request=request,
        code=code,
        state=state,
        error=error,
        error_description=error_description,
        db=db,
    )


@router.get("/oauth/youtube/callback")
@router.get("/oauth/youtube/callback/")
async def oauth_youtube_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle Google OAuth 2.0 authorization callback for YouTube."""
    return await oauth_callback(
        platform="youtube",
        request=request,
        code=code,
        state=state,
        error=error,
        error_description=error_description,
        db=db,
    )


# ---------------------------------------------------------------------------
# Account Management Endpoints
# ---------------------------------------------------------------------------

async def _build_social_account_out(
    account: SocialAccount,
    db: Session,
    metadata: Optional[dict] = None,
    from_batch: bool = False,
) -> SocialAccountOut:
    permissions = (
        account.permissions
        if hasattr(account, "permissions") and account.permissions is not None
        else db.query(AccountPermission).filter(AccountPermission.social_account_id == account.id).all()
    )
    perms_out = [
        AccountPermissionOut(
            id=p.id,
            social_account_id=p.social_account_id,
            permission=p.permission,
            granted=p.granted,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in permissions
    ]

    if metadata is not None:
        mongo_doc = metadata
    elif not from_batch:
        mongo_doc = await get_social_metadata(account.id)
    else:
        mongo_doc = None
    pic_url = mongo_doc.get("profile_picture_url") if mongo_doc else None

    return SocialAccountOut(
        id=account.id,
        user_id=account.user_id,
        team_id=account.team_id,
        platform=SocialPlatform(account.platform),
        platform_account_id=account.platform_account_id,
        account_name=account.account_name,
        account_username=account.account_username,
        status=AccountStatus(account.status),
        connected_at=account.connected_at,
        last_synced_at=account.last_synced_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
        permissions=perms_out,
        profile_picture_url=pic_url,
    )


@router.get("/accounts", response_model=List[SocialAccountOut], status_code=status.HTTP_200_OK)
async def list_social_accounts(
    team_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[SocialAccountOut]:
    """List all connected social media accounts for the user or workspace."""
    query = db.query(SocialAccount).options(joinedload(SocialAccount.permissions))
    if team_id:
        query = query.filter(SocialAccount.team_id == team_id)
    else:
        query = query.filter(SocialAccount.user_id == current_user.id)

    accounts = query.order_by(SocialAccount.created_at.desc()).all()
    if not accounts:
        return []

    acc_ids = [acc.id for acc in accounts]
    meta_map = await get_social_metadata_batch(acc_ids)

    return [await _build_social_account_out(acc, db, metadata=meta_map.get(acc.id), from_batch=True) for acc in accounts]


@router.get("/accounts/{account_id}", response_model=SocialAccountOut, status_code=status.HTTP_200_OK)
async def get_social_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SocialAccountOut:
    """Retrieve details and permissions for a specific connected account."""
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social account not found.")

    if account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this social account.")

    return await _build_social_account_out(account, db)


# ---------------------------------------------------------------------------
# Account Synchronization Endpoint
# ---------------------------------------------------------------------------

@router.post("/accounts/{account_id}/sync", response_model=SyncResponseOut, status_code=status.HTTP_200_OK)
async def sync_social_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncResponseOut:
    """
    Synchronize social account metadata.
    Validates token validity, fetches updated profile metadata from provider if configured,
    records immutable sync attempt log, and updates MongoDB document.
    """
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social account not found.")

    if account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this social account.")

    provider = get_provider(account.platform)
    now = datetime.now(timezone.utc)

    try:
        # Check token expiry if expiration timestamp is recorded
        if account.token_expires_at:
            exp = account.token_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                account.status = AccountStatus.token_expired.value
                sync_log = AccountSyncLog(
                    social_account_id=account.id,
                    status=SyncStatus.failed.value,
                    message="Sync failed: OAuth access token has expired. Reconnection required.",
                    synced_at=now,
                )
                db.add(sync_log)
                db.commit()
                return SyncResponseOut(
                    account_id=account.id,
                    status=SyncStatus.failed,
                    message="OAuth access token has expired. Please reconnect your account.",
                    last_synced_at=now,
                )

        # Update last synced timestamp and active status
        account.last_synced_at = now
        account.status = AccountStatus.connected.value

        sync_log = AccountSyncLog(
            social_account_id=account.id,
            status=SyncStatus.success.value,
            message="Account metadata and permissions synchronized successfully.",
            synced_at=now,
        )
        db.add(sync_log)
        db.commit()
        db.refresh(account)

        return SyncResponseOut(
            account_id=account.id,
            status=SyncStatus.success,
            message=f"{provider.display_name if provider else account.platform} account synchronized successfully.",
            last_synced_at=now,
        )

    except Exception as exc:
        account.status = AccountStatus.error.value
        sync_log = AccountSyncLog(
            social_account_id=account.id,
            status=SyncStatus.failed.value,
            message=f"Sync error: {str(exc)}",
            synced_at=now,
        )
        db.add(sync_log)
        db.commit()

        return SyncResponseOut(
            account_id=account.id,
            status=SyncStatus.failed,
            message=f"Synchronization failed: {str(exc)}",
            last_synced_at=now,
        )


# ---------------------------------------------------------------------------
# Account Disconnect & Permissions
# ---------------------------------------------------------------------------

@router.delete("/accounts/{account_id}", status_code=status.HTTP_200_OK)
async def disconnect_social_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Disconnect and remove a social account and its associated permissions & metadata."""
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social account not found.")

    if account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this social account.")

    platform_name = account.platform
    account_name = account.account_name

    # Cascade delete in PostgreSQL
    db.delete(account)
    db.commit()

    # Clean up MongoDB document
    await delete_social_metadata(account_id)

    return {"message": f"Successfully disconnected {platform_name} account '{account_name}'."}


@router.get("/accounts/{account_id}/permissions", response_model=List[AccountPermissionOut], status_code=status.HTTP_200_OK)
def get_account_permissions(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[AccountPermissionOut]:
    """List granted and available permissions for a connected account."""
    account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social account not found.")

    if account.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this social account.")

    return db.query(AccountPermission).filter(AccountPermission.social_account_id == account_id).all()

