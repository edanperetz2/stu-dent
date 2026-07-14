import uuid

from app.models.notification import NotificationType
from app.services.notifications import notify
from tests.helpers import auth_header, create_and_login_patient, register_and_login


def _notify_user(db_session, user_id, message="Test notification"):
    entry = notify(
        db_session,
        notification_type=NotificationType.appointment_reminder,
        message=message,
        recipient_id=user_id,
    )
    db_session.commit()
    return entry


def test_user_sees_own_notifications(client, db_session):
    student_token = register_and_login(client, "notif-s1@example.com", role="student")
    user_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    _notify_user(db_session, uuid.UUID(user_id))

    response = client.get("/notifications", headers=auth_header(student_token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["message"] == "Test notification"
    assert body[0]["read_at"] is None


def test_patient_sees_own_notifications(client, db_session):
    student_token = register_and_login(client, "notif-s2@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "notif-p2@example.com"
    )
    _notify_user(db_session, uuid.UUID(patient_id))

    response = client.get("/notifications", headers=auth_header(patient_token))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_notifications_ordered_newest_first(client, db_session):
    student_token = register_and_login(client, "notif-s3@example.com", role="student")
    user_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    _notify_user(db_session, uuid.UUID(user_id), message="first")
    _notify_user(db_session, uuid.UUID(user_id), message="second")

    response = client.get("/notifications", headers=auth_header(student_token))
    body = response.json()
    assert len(body) == 2
    assert body[0]["message"] == "second"
    assert body[1]["message"] == "first"


def test_mark_notification_read(client, db_session):
    student_token = register_and_login(client, "notif-s4@example.com", role="student")
    user_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    entry = _notify_user(db_session, uuid.UUID(user_id))

    response = client.post(f"/notifications/{entry.id}/read", headers=auth_header(student_token))
    assert response.status_code == 200
    assert response.json()["read_at"] is not None

    # idempotent: marking again doesn't error
    again = client.post(f"/notifications/{entry.id}/read", headers=auth_header(student_token))
    assert again.status_code == 200


def test_mark_notification_unread(client, db_session):
    student_token = register_and_login(client, "notif-s4b@example.com", role="student")
    user_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    entry = _notify_user(db_session, uuid.UUID(user_id))

    client.post(f"/notifications/{entry.id}/read", headers=auth_header(student_token))
    unread_response = client.post(
        f"/notifications/{entry.id}/unread", headers=auth_header(student_token)
    )
    assert unread_response.status_code == 200
    assert unread_response.json()["read_at"] is None

    # idempotent: marking unread again doesn't error
    again = client.post(f"/notifications/{entry.id}/unread", headers=auth_header(student_token))
    assert again.status_code == 200
    assert again.json()["read_at"] is None


def test_unread_only_filter(client, db_session):
    student_token = register_and_login(client, "notif-s5@example.com", role="student")
    user_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    first = _notify_user(db_session, uuid.UUID(user_id), message="first")
    _notify_user(db_session, uuid.UUID(user_id), message="second")

    client.post(f"/notifications/{first.id}/read", headers=auth_header(student_token))

    response = client.get("/notifications?unread_only=true", headers=auth_header(student_token))
    body = response.json()
    assert len(body) == 1
    assert body[0]["message"] == "second"


def test_cannot_read_others_notification(client, db_session):
    student_a_token = register_and_login(client, "notif-s6a@example.com", role="student")
    student_b_token = register_and_login(client, "notif-s6b@example.com", role="student")
    user_a_id = client.get("/users/me", headers=auth_header(student_a_token)).json()["id"]
    entry = _notify_user(db_session, uuid.UUID(user_a_id))

    response = client.post(f"/notifications/{entry.id}/read", headers=auth_header(student_b_token))
    assert response.status_code == 404


def test_notifications_require_authentication(client):
    assert client.get("/notifications").status_code == 401
    assert client.post(f"/notifications/{uuid.uuid4()}/read").status_code == 401


def test_notifications_scoped_per_recipient(client, db_session):
    student_a_token = register_and_login(client, "notif-s7a@example.com", role="student")
    student_b_token = register_and_login(client, "notif-s7b@example.com", role="student")
    user_a_id = client.get("/users/me", headers=auth_header(student_a_token)).json()["id"]
    _notify_user(db_session, uuid.UUID(user_a_id))

    response = client.get("/notifications", headers=auth_header(student_b_token))
    assert response.status_code == 200
    assert response.json() == []
