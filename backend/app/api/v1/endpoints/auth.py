"""
app/api/v1/endpoints/auth.py
-----------------------------
Authentication endpoints:
  POST   /api/v1/auth/register   — create a new account
  POST   /api/v1/auth/login      — obtain a JWT
  GET    /api/v1/auth/me         — return the current user's profile
  POST   /api/v1/auth/logout     — stateless logout (client discards token)
"""

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
