"""
tests/test_email_and_notifications.py
-------------------------------------
Automated test suite for Real Email & Notification Module (Milestone 4).
Tests:
- Notification Preferences GET & PUT
- Real Email Service (SMTP, TLS/SSL, HTML templates)
- Safe SMTP error handling & secret sanitization
- Asynchronous Celery Email Task (send_notification_email_task)
- Idempotency & duplicate prevention across retries and refreshes
- Scheduled Post Reminders
- Post Published & Post Failed notifications
- Authenticated Test Email endpoint
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest

from app.models.user import User
from app.models.user_settings import UserSettings
from app.models.post import Post
from app.models.notification import Notification
from app.models.enums import PostStatus
from app.services.auth_service import hash_password, create_access_token
from app.services.email_service import EmailService, EmailTemplates, sanitize_email_error
from app.services.notification_service import (
    NotificationType,
    create_notification,
    create_post_notification,
    notify_post_published,
    notify_post_failed,
    notify_scheduled_reminder,
    notify_campaign_event,
    notify_account_issue,
    notify_system_alert,
    get_user_preferences,
    update_user_preferences,
)
from app.worker.tasks import send_notification_email_task, check_and_send_scheduled_reminders


@pytest.fixture
def email_test_user(db_session):
    user = User(
        email="testuser@example.com",
        hashed_password=hash_password("securepassword123"),
        full_name="Alex Rivera",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    settings = UserSettings(
        user_id=user.id,
        email_notifications=True,
        timezone="America/New_York",
    )
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)

    return user


@pytest.fixture
def auth_headers(email_test_user):
    token = create_access_token(subject=str(email_test_user.id))
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Preferences API Tests
# ---------------------------------------------------------------------------
def test_get_and_update_notification_preferences(client, email_test_user, auth_headers):
    # GET preferences
    resp = client.get("/api/v1/notifications/preferences", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email_notifications"] is True
    assert "post_published" in data["preferences"]
    assert data["preferences"]["post_published"]["in_app"] is True
    assert data["preferences"]["post_published"]["email"] is True

    # PUT preferences — disable email for campaigns
    update_payload = {
        "email_notifications": True,
        "preferences": {
            "campaign_event": {"in_app": True, "email": False},
            "post_published": {"in_app": True, "email": True},
        },
    }
    put_resp = client.put("/api/v1/notifications/preferences", json=update_payload, headers=auth_headers)
    assert put_resp.status_code == 200
    updated_data = put_resp.json()
    assert updated_data["preferences"]["campaign_event"]["email"] is False
    assert updated_data["preferences"]["campaign_event"]["in_app"] is True


# ---------------------------------------------------------------------------
# 2. Email Service Tests (Mocked SMTP)
# ---------------------------------------------------------------------------
def test_email_service_send_email_success():
    with patch("app.core.config.settings.SMTP_HOST", "smtp.gmail.com"), \
         patch("app.core.config.settings.SMTP_PORT", 587), \
         patch("app.core.config.settings.SMTP_USERNAME", "sender@gmail.com"), \
         patch("app.core.config.settings.SMTP_PASSWORD", "app-password-1234"), \
         patch("app.core.config.settings.SMTP_FROM_EMAIL", "sender@gmail.com"), \
         patch("app.core.config.settings.SMTP_USE_TLS", True), \
         patch("smtplib.SMTP") as mock_smtp_cls:

        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        subject, html_body, text_body = EmailTemplates.post_published(
            user_name="Alex",
            platform="instagram",
            preview="Exciting product launch!",
            published_url="https://instagram.com/p/12345",
        )

        success, err = EmailService.send_email(
            to_email="recipient@example.com",
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

        assert success is True
        assert err is None
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("sender@gmail.com", "app-password-1234")
        mock_smtp.sendmail.assert_called_once()


def test_email_service_authentication_error():
    import smtplib
    with patch("app.core.config.settings.SMTP_HOST", "smtp.gmail.com"), \
         patch("app.core.config.settings.SMTP_PORT", 587), \
         patch("app.core.config.settings.SMTP_USERNAME", "sender@gmail.com"), \
         patch("app.core.config.settings.SMTP_PASSWORD", "secret-password"), \
         patch("smtplib.SMTP") as mock_smtp_cls:

        mock_smtp = MagicMock()
        mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp

        success, err = EmailService.send_email(
            to_email="recipient@example.com",
            subject="Test Subject",
            html_body="<p>Test</p>",
        )

        assert success is False
        assert "SMTP Authentication Error" in err
        # Ensure password is not exposed
        assert "secret-password" not in err


def test_sanitize_email_error():
    sensitive = "Failed: password=supersecretpass123, token=bearer_xyz789"
    sanitized = sanitize_email_error(sensitive)
    assert "supersecretpass123" not in sanitized
    assert "[REDACTED]" in sanitized


# ---------------------------------------------------------------------------
# 3. Celery Email Task End-to-End Test
# ---------------------------------------------------------------------------
from tests.conftest import TestingSessionLocal


def test_send_notification_email_task_success(db_session, email_test_user):
    notif = Notification(
        user_id=email_test_user.id,
        type=NotificationType.POST_PUBLISHED,
        title="Post Published",
        message="Your post was published",
        meta_data={"platform": "twitter", "preview": "Hello world"},
        email_status="pending",
    )
    db_session.add(notif)
    db_session.commit()
    notif_id = notif.id

    with patch("app.worker.tasks.SessionLocal", side_effect=TestingSessionLocal), \
         patch.object(EmailService, "send_email", return_value=(True, None)) as mock_send:
        result = send_notification_email_task(notif_id)

        assert result["status"] == "sent"
        assert result["recipient"] == email_test_user.email
        mock_send.assert_called_once()

        fresh_db = TestingSessionLocal()
        try:
            updated_notif = fresh_db.query(Notification).filter(Notification.id == notif_id).first()
            assert updated_notif.email_status == "sent"
            assert updated_notif.email_sent_at is not None
            assert updated_notif.email_error is None
        finally:
            fresh_db.close()


def test_send_notification_email_task_skipped_when_disabled(db_session, email_test_user):
    # Disable email for post_published
    settings = db_session.query(UserSettings).filter(UserSettings.user_id == email_test_user.id).first()
    settings.set_notification_preferences({
        "post_published": {"in_app": True, "email": False}
    })
    db_session.commit()

    notif = Notification(
        user_id=email_test_user.id,
        type=NotificationType.POST_PUBLISHED,
        title="Post Published",
        message="Your post was published",
        email_status="pending",
    )
    db_session.add(notif)
    db_session.commit()
    notif_id = notif.id

    with patch("app.worker.tasks.SessionLocal", side_effect=TestingSessionLocal), \
         patch.object(EmailService, "send_email") as mock_send:
        result = send_notification_email_task(notif_id)

        assert result["status"] == "skipped"
        mock_send.assert_not_called()

        fresh_db = TestingSessionLocal()
        try:
            updated_notif = fresh_db.query(Notification).filter(Notification.id == notif_id).first()
            assert updated_notif.email_status == "skipped"
        finally:
            fresh_db.close()


def test_send_notification_email_task_idempotency(db_session, email_test_user):
    # If already marked sent, do not re-send
    notif = Notification(
        user_id=email_test_user.id,
        type=NotificationType.POST_PUBLISHED,
        title="Post Published",
        message="Your post was published",
        email_status="sent",
        email_sent_at=datetime.now(timezone.utc),
    )
    db_session.add(notif)
    db_session.commit()
    notif_id = notif.id

    with patch("app.worker.tasks.SessionLocal", side_effect=TestingSessionLocal), \
         patch.object(EmailService, "send_email") as mock_send:
        result = send_notification_email_task(notif_id)
        assert result["status"] == "already_sent"
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Scheduled Reminder Task Tests
# ---------------------------------------------------------------------------
def test_check_and_send_scheduled_reminders(db_session, email_test_user):
    now = datetime.now(timezone.utc)
    # Create a post scheduled 15 minutes from now
    post = Post(
        user_id=email_test_user.id,
        content="Upcoming launch post in 15 mins",
        status=PostStatus.scheduled.value,
        scheduled_at=now + timedelta(minutes=15),
    )
    db_session.add(post)
    db_session.commit()
    post_id = post.id
    user_id = email_test_user.id

    with patch("app.worker.tasks.SessionLocal", side_effect=TestingSessionLocal), \
         patch("app.services.notification_service._dispatch_email_task_safely") as mock_dispatch:
        res = check_and_send_scheduled_reminders()
        assert res["dispatched_count"] >= 1
        assert post_id in res["post_ids"]

        # Run again — idempotency prevents duplicate reminder
        res2 = check_and_send_scheduled_reminders()
        fresh_db = TestingSessionLocal()
        try:
            notifs = fresh_db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.type == NotificationType.SCHEDULED_REMINDER,
            ).all()
            assert len(notifs) == 1
        finally:
            fresh_db.close()


# ---------------------------------------------------------------------------
# 5. Authenticated Test Email API Endpoint
# ---------------------------------------------------------------------------
def test_test_email_api_endpoint(client, email_test_user, auth_headers):
    with patch.object(EmailService, "send_email", return_value=(True, None)):
        resp = client.post("/api/v1/notifications/test-email", json={}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["recipient"] == email_test_user.email
        assert "Test email sent successfully" in data["message"]
