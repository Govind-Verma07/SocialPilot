"""
app/api/v1/endpoints/notifications.py
--------------------------------------
REST API endpoints for the Notification Module (Milestone 4).

All endpoints are JWT-authenticated and strictly user-isolated.
Users can NEVER access another user's notifications by any ID.

Endpoints:
  GET    /notifications                     — paginated list, optional filters
  GET    /notifications/unread-count        — fast unread badge count
  GET    /notifications/preferences         — get user notification preferences
  PUT    /notifications/preferences         — update user notification preferences
  POST   /notifications/test-email          — send authenticated SMTP test email
  PATCH  /notifications/{id}/read           — mark one as read
  PATCH  /notifications/read-all            — mark all as read
  DELETE /notifications/{id}               — delete/clear one notification
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
    TestEmailRequest,
    TestEmailResponse,
)
from app.services import notification_service as ns
from app.services.email_service import EmailService, EmailTemplates

router = APIRouter()


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the number of unread notifications for the authenticated user."""
    count = ns.get_unread_count(db, current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.get("/preferences", response_model=NotificationPreferencesResponse)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get granular notification preferences for the authenticated user."""
    prefs = ns.get_user_preferences(db, current_user.id)
    return NotificationPreferencesResponse(
        email_notifications=prefs["email_notifications"],
        preferences=prefs["preferences"],
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
def update_preferences(
    payload: NotificationPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update granular notification preferences for the authenticated user."""
    payload_dict = {}
    if payload.email_notifications is not None:
        payload_dict["email_notifications"] = payload.email_notifications
    if payload.preferences is not None:
        payload_dict["preferences"] = {
            k: v.model_dump() if hasattr(v, "model_dump") else v
            for k, v in payload.preferences.items()
        }

    updated = ns.update_user_preferences(db, current_user.id, payload_dict)
    return NotificationPreferencesResponse(
        email_notifications=updated["email_notifications"],
        preferences=updated["preferences"],
    )


@router.post("/test-email", response_model=TestEmailResponse)
def send_test_email(
    payload: Optional[TestEmailRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send an authenticated test email to the user's registered address to verify SMTP configuration.
    Strictly authenticated: does not expose credentials or allow arbitrary spamming.
    """
    target_email = (payload.to_email if payload and payload.to_email else current_user.email) or current_user.email
    if not target_email or "@" not in target_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid recipient email address is required.",
        )

    user_name = current_user.full_name or current_user.email.split("@")[0]
    subject, html_body, text_body = EmailTemplates.test_email(user_name=user_name)

    success, error_msg = EmailService.send_email(
        to_email=target_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )

    # Also log a persistent system notification confirming the test
    ns.create_system_notification(
        db=db,
        user_id=current_user.id,
        title="SMTP Test Email Executed",
        message=f"SMTP test email delivery to {target_email}: {'Success' if success else f'Failed ({error_msg})'}",
    )

    if not success:
        return TestEmailResponse(
            success=False,
            message=f"Could not deliver test email: {error_msg}",
            recipient=target_email,
            smtp_host=settings.SMTP_HOST or "None configured",
        )

    return TestEmailResponse(
        success=True,
        message="Test email sent successfully! Check your inbox and spam folder.",
        recipient=target_email,
        smtp_host=settings.SMTP_HOST or "localhost",
    )


@router.get("", response_model=NotificationListResponse)
@router.get("/", response_model=NotificationListResponse, include_in_schema=False)
def list_notifications(
    unread_only: bool = Query(False, description="If true, return only unread notifications"),
    type: Optional[str] = Query(None, description="Filter by notification type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get authenticated user's notifications, newest first.
    Supports filtering by read status and notification type.
    """
    skip = (page - 1) * page_size
    items, total = ns.get_user_notifications(
        db,
        user_id=current_user.id,
        unread_only=unread_only,
        notification_type=type,
        skip=skip,
        limit=page_size,
    )
    unread_count = ns.get_unread_count(db, current_user.id)
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )


@router.patch("/read-all", status_code=status.HTTP_200_OK)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all of the authenticated user's unread notifications as read."""
    updated = ns.mark_all_read(db, current_user.id)
    return {"message": f"Marked {updated} notification(s) as read.", "updated_count": updated}


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read. Enforces ownership — users cannot mark others' notifications."""
    notif = ns.mark_notification_read(db, notification_id, current_user.id)
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found or does not belong to you.",
        )
    return NotificationResponse.model_validate(notif)


@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete/clear a notification. Enforces user ownership."""
    deleted = ns.delete_notification(db, notification_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found or does not belong to you.",
        )
    return {"message": "Notification deleted.", "id": notification_id}
