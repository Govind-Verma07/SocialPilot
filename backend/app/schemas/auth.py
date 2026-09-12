"""
app/schemas/auth.py
--------------------
Pydantic v2 schemas for authentication endpoints.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import UserRole


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    """Payload for POST /auth/register."""
    full_name: str = Field(..., min_length=2, max_length=150, examples=["Jane Doe"])
    email: EmailStr = Field(..., examples=["jane@example.com"])
    password: str = Field(..., min_length=8, max_length=100, examples=["Str0ng#Pass!"])
    role: UserRole = Field(default=UserRole.content_creator, examples=["content_creator"])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Lowercase + strip whitespace for consistent storage."""
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v

    @field_validator("role")
    @classmethod
    def validate_public_role(cls, v: UserRole) -> UserRole:
        allowed_roles = {
            UserRole.content_creator,
            UserRole.marketing_team,
            UserRole.business_user,
        }
        if v not in allowed_roles:
            raise ValueError("Administrator role cannot be registered publicly.")
        return v


class UserLogin(BaseModel):
    """Payload for POST /auth/login."""
    email: EmailStr = Field(..., examples=["jane@example.com"])
    password: str = Field(..., examples=["Str0ng#Pass!"])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResetPassword(BaseModel):
    """Payload for POST /auth/reset-password."""
    email: EmailStr = Field(..., examples=["jane@example.com"])
    new_password: str = Field(..., min_length=8, max_length=100, examples=["NewStr0ng#Pass!"])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class UserOut(BaseModel):
    """User profile returned by the API (never exposes hashed_password)."""
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """JWT access token response."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str          # user ID
    exp: Optional[int] = None
