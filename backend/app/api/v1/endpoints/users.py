"""
app/api/v1/endpoints/users.py
------------------------------
User profile and settings endpoints:
  GET    /api/v1/users/me           — retrieve current user profile
  PATCH  /api/v1/users/me           — update allowed profile fields (full_name)
  GET    /api/v1/users/me/settings  — retrieve current user settings
  PUT    /api/v1/users/me/settings  — update current user settings
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.user_settings import UserSettings
from app.schemas.auth import UserOut
from app.schemas.user import UserSettingsOut, UserSettingsUpdate, UserUpdate
from app.services.auth_service import get_current_user

router = APIRouter()


@router.get(
    "/me",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
def get_my_profile(current_user: User = Depends(get_current_user)) -> UserOut:
    """Return the profile information for the authenticated user."""
    return UserOut.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserOut,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
)
def update_my_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    """
    Update profile fields for the authenticated user.
    Only allows editing mutable profile fields like `full_name`.
    Security/RBAC fields (role, is_active, email, hashed_password) cannot be modified.
    """
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.get(
    "/me/settings",
    response_model=UserSettingsOut,
    status_code=status.HTTP_200_OK,
    summary="Get current user settings",
)
def get_my_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsOut:
    """Return settings for the authenticated user, automatically creating default settings if none exist."""
    settings_obj = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=current_user.id)
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return UserSettingsOut.model_validate(settings_obj)


@router.put(
    "/me/settings",
    response_model=UserSettingsOut,
    status_code=status.HTTP_200_OK,
    summary="Update current user settings",
)
def update_my_settings(
    payload: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserSettingsOut:
    """Update settings (timezone, email notifications, extra preferences) for the authenticated user."""
    settings_obj = db.query(UserSettings).filter(UserSettings.user_id == current_user.id).first()
    if not settings_obj:
        settings_obj = UserSettings(user_id=current_user.id)
        db.add(settings_obj)

    if payload.email_notifications is not None:
        settings_obj.email_notifications = payload.email_notifications
    if payload.timezone is not None:
        settings_obj.timezone = payload.timezone.strip()
    if payload.extra is not None:
        settings_obj.extra = payload.extra

    db.commit()
    db.refresh(settings_obj)
    return UserSettingsOut.model_validate(settings_obj)
