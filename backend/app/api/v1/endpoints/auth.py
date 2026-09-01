"""
app/api/v1/endpoints/auth.py
-----------------------------
Authentication endpoints:
  POST   /api/v1/auth/register   — create a new account
  POST   /api/v1/auth/login      — obtain a JWT
  GET    /api/v1/auth/me         — return the current user's profile
  POST   /api/v1/auth/logout     — stateless logout (client discards token)
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token, UserCreate, UserLogin, UserOut
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> Token:
    """
    Register a new user.

    - Validates that the email is not already taken.
    - Hashes the password with bcrypt.
    - Returns a JWT access token immediately so the user is logged in.
    """
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role.value if hasattr(payload.role, 'value') else payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Log in and receive a JWT",
)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """
    Authenticate an existing user.

    Returns a JWT on success; 401 on bad credentials (message is intentionally
    vague to avoid user-enumeration attacks).
    """
    user: User | None = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been disabled.",
        )

    token = create_access_token(subject=user.id)
    return Token(access_token=token, user=UserOut.model_validate(user))


# ---------------------------------------------------------------------------
# Me (protected)
# ---------------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Get the current user's profile",
)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the authenticated user's profile information."""
    return UserOut.model_validate(current_user)


# ---------------------------------------------------------------------------
# Logout (stateless — client drops the token)
# ---------------------------------------------------------------------------
@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out (invalidate token client-side)",
)
def logout(_current_user: User = Depends(get_current_user)) -> dict:
    """
    Logout endpoint.

    Because JWTs are stateless, the server cannot truly invalidate a token
    without a blocklist.  This endpoint validates the token is still good
    and returns a 200 so the client knows it's safe to discard the token.
    """
    return {"message": "Successfully logged out."}


# ---------------------------------------------------------------------------
# Google OAuth 2.0 Login Endpoints
# ---------------------------------------------------------------------------
import secrets
import uuid
from urllib.parse import urlencode, quote
from fastapi import Query, Request
from fastapi.responses import RedirectResponse
import httpx
from app.core.config import settings
from app.models.enums import UserRole

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/url", summary="Get Google OAuth authorization URL")
def get_google_auth_url(request: Request) -> dict:
    """
    Generate Google OAuth authorization redirect URL for user sign-in.
    Returns is_configured=False if GOOGLE_CLIENT_ID is empty in .env.
    """
    client_id = (settings.GOOGLE_CLIENT_ID or "").strip()
    client_secret = (settings.GOOGLE_CLIENT_SECRET or "").strip()

    if not client_id or not client_secret:
        return {
            "is_configured": False,
            "message": "Google OAuth credentials are not configured in backend .env.",
        }

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = settings.GOOGLE_REDIRECT_URI or f"{base_url}{settings.API_V1_PREFIX}/auth/google/callback"
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return {
        "is_configured": True,
        "authorization_url": auth_url,
    }


@router.get("/google/callback", summary="Handle Google OAuth login callback")
async def google_oauth_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Process Google OAuth callback. Exchanges code for tokens, fetches user profile,
    links or creates user account with default role (never Administrator),
    generates application JWT, and redirects to frontend.
    """
    frontend_base = settings.allowed_origins_list[0] if settings.allowed_origins_list else "http://localhost:5173"

    if error:
        err_msg = quote(error_description or error or "Google login was cancelled or failed.")
        return RedirectResponse(f"{frontend_base}/login?error={err_msg}")

    if not code:
        err_msg = quote("Missing code parameter in Google OAuth callback.")
        return RedirectResponse(f"{frontend_base}/login?error={err_msg}")

    client_id = (settings.GOOGLE_CLIENT_ID or "").strip()
    client_secret = (settings.GOOGLE_CLIENT_SECRET or "").strip()

    if not client_id or not client_secret:
        err_msg = quote("Google OAuth credentials not configured on backend.")
        return RedirectResponse(f"{frontend_base}/login?error={err_msg}")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = settings.GOOGLE_REDIRECT_URI or f"{base_url}{settings.API_V1_PREFIX}/auth/google/callback"

    try:
        # 1. Code Exchange
        token_data = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient() as client:
            token_resp = await client.post(GOOGLE_TOKEN_URL, data=token_data)
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access_token = tokens.get("access_token")

            if not access_token:
                raise ValueError("No access_token returned by Google.")

            # 2. Fetch Google profile
            userinfo_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            google_profile = userinfo_resp.json()

        google_email = google_profile.get("email")
        google_name = google_profile.get("name") or (google_email.split("@")[0] if google_email else "User")
        email_verified = google_profile.get("email_verified", False)

        if not google_email:
            raise ValueError("No email returned in Google profile.")

        if not email_verified:
            err_msg = quote("Google account email is not verified.")
            return RedirectResponse(f"{frontend_base}/login?error={err_msg}")

        # 3. User Lookup or Auto-Create (Preserve existing RBAC, default: content_creator, never admin)
        user = db.query(User).filter(User.email == google_email).first()
        if user:
            if not user.is_active:
                err_msg = quote("Your account has been disabled.")
                return RedirectResponse(f"{frontend_base}/login?error={err_msg}")
        else:
            user = User(
                email=google_email,
                full_name=google_name,
                hashed_password=hash_password(str(uuid.uuid4())),
                role=UserRole.content_creator.value,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # 4. Generate Application JWT Token
        jwt_token = create_access_token(subject=user.id)

        # 5. Redirect to Frontend with Token
        user_role_val = user.role.value if hasattr(user.role, 'value') else str(user.role)
        query_params = urlencode({
            "google_token": jwt_token,
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user_role_val,
        })
        return RedirectResponse(f"{frontend_base}/login?{query_params}")

    except Exception as exc:
        err_msg = quote(f"Google authentication error: {str(exc)}")
        return RedirectResponse(f"{frontend_base}/login?error={err_msg}")

