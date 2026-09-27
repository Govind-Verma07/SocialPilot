import pytest
from app.models.user import User
from app.models.notification import Notification
from app.services.auth_service import hash_password, create_access_token
from app.services.notification_service import (
    NotificationType,
    create_notification,
    create_post_notification,
    create_campaign_notification,
    get_user_notifications,
    get_unread_count,
    mark_notification_read,
    mark_all_read,
    delete_notification,
)


@pytest.fixture
def test_users(db_session):
    user1 = User(
        email="user1@example.com",
        hashed_password=hash_password("password123"),
        full_name="User One",
        is_active=True,
    )
    user2 = User(
        email="user2@example.com",
        hashed_password=hash_password("password123"),
        full_name="User Two",
        is_active=True,
    )
    db_session.add_all([user1, user2])
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    return user1, user2


@pytest.fixture
def auth_headers_user1(test_users):
    user1, _ = test_users
    token = create_access_token(subject=str(user1.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user2(test_users):
    _, user2 = test_users
    token = create_access_token(subject=str(user2.id))
    return {"Authorization": f"Bearer {token}"}


def test_create_and_get_notification(db_session, test_users):
    user1, _ = test_users
    notif = create_notification(
        db=db_session,
        user_id=user1.id,
        type=NotificationType.SYSTEM_ALERT,
        title="Test Alert",
        message="System maintenance scheduled",
    )
    assert notif.id is not None
    assert notif.user_id == user1.id
    assert notif.is_read is False

    notifications, total = get_user_notifications(db_session, user_id=user1.id)
    assert total == 1
    assert len(notifications) == 1
    assert notifications[0].title == "Test Alert"


def test_user_isolation(db_session, test_users, client, auth_headers_user1, auth_headers_user2):
    user1, user2 = test_users
    create_notification(
        db=db_session,
        user_id=user1.id,
        type=NotificationType.POST_PUBLISHED,
        title="User1 Post",
        message="Post published",
    )
    create_notification(
        db=db_session,
        user_id=user2.id,
        type=NotificationType.POST_PUBLISHED,
        title="User2 Post",
        message="Post published",
    )

    # User 1 should only see user 1's notification
    resp1 = client.get("/api/v1/notifications", headers=auth_headers_user1)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["total"] == 1
    assert data1["items"][0]["title"] == "User1 Post"

    # User 2 should only see user 2's notification
    resp2 = client.get("/api/v1/notifications", headers=auth_headers_user2)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 1
    assert data2["items"][0]["title"] == "User2 Post"


def test_auth_required(client):
    resp = client.get("/api/v1/notifications")
    assert resp.status_code in [401, 403]


def test_unread_count_and_mark_as_read(db_session, test_users, client, auth_headers_user1):
    user1, _ = test_users
    n1 = create_notification(
        db=db_session,
        user_id=user1.id,
        type=NotificationType.POST_PUBLISHED,
        title="Post 1",
        message="Msg 1",
    )
    n2 = create_notification(
        db=db_session,
        user_id=user1.id,
        type=NotificationType.POST_FAILED,
        title="Post 2",
        message="Msg 2",
    )

    resp = client.get("/api/v1/notifications/unread-count", headers=auth_headers_user1)
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 2

    # Mark n1 as read
    patch_resp = client.patch(f"/api/v1/notifications/{n1.id}/read", headers=auth_headers_user1)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_read"] is True

    # Check unread count is now 1
    resp = client.get("/api/v1/notifications/unread-count", headers=auth_headers_user1)
    assert resp.json()["unread_count"] == 1

    # Mark all as read
    patch_all = client.patch("/api/v1/notifications/read-all", headers=auth_headers_user1)
    assert patch_all.status_code == 200
    assert patch_all.json()["updated_count"] == 1

    resp = client.get("/api/v1/notifications/unread-count", headers=auth_headers_user1)
    assert resp.json()["unread_count"] == 0


def test_delete_notification(db_session, test_users, client, auth_headers_user1, auth_headers_user2):
    user1, user2 = test_users
    n1 = create_notification(
        db=db_session,
        user_id=user1.id,
        type=NotificationType.POST_PUBLISHED,
        title="Post 1",
        message="Msg 1",
    )

    # User 2 cannot delete user 1's notification
    del_resp2 = client.delete(f"/api/v1/notifications/{n1.id}", headers=auth_headers_user2)
    assert del_resp2.status_code == 404

    # User 1 can delete
    del_resp1 = client.delete(f"/api/v1/notifications/{n1.id}", headers=auth_headers_user1)
    assert del_resp1.status_code == 200

    resp = client.get("/api/v1/notifications", headers=auth_headers_user1)
    assert resp.json()["total"] == 0


def test_duplicate_prevention(db_session, test_users):
    user1, _ = test_users
    # First post notification
    n1 = create_post_notification(
        db=db_session,
        user_id=user1.id,
        post_id="999",
        event="published",
        platform="Instagram",
    )
    assert n1 is not None

    # Repeated trigger with same post_id and status should return existing notification
    n2 = create_post_notification(
        db=db_session,
        user_id=user1.id,
        post_id="999",
        event="published",
        platform="Instagram",
    )
    assert n2.id == n1.id

    # Total notifications in DB for user should still be 1
    notifications, total = get_user_notifications(db_session, user_id=user1.id)
    assert total == 1


def test_campaign_notification(db_session, test_users, client, auth_headers_user1):
    user1, _ = test_users
    n = create_campaign_notification(
        db=db_session,
        user_id=user1.id,
        campaign_id="42",
        campaign_name="Summer Sale 2026",
        event="created",
    )
    assert n.related_entity_type == "campaign"
    assert n.related_entity_id == "42"

    resp = client.get("/api/v1/notifications?type=campaign_created", headers=auth_headers_user1)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["related_entity_type"] == "campaign"
    assert items[0]["related_entity_id"] == "42"
