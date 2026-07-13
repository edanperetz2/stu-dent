from datetime import UTC, datetime, timedelta

from app.jobs.reactivation import reactivate_expired_deactivations
from app.models.equipment import Equipment
from app.models.room import Room
from tests.helpers import auth_header, create_patient, register_and_login


def _admin_token(client, email="rooms-admin1@example.com"):
    return register_and_login(client, email, role="admin")


def test_admin_can_create_and_list_room(client):
    token = _admin_token(client)
    create_response = client.post(
        "/admin/rooms", json={"name": "Room 101"}, headers=auth_header(token)
    )
    assert create_response.status_code == 201
    assert create_response.json()["is_active"] is True

    list_response = client.get("/admin/rooms", headers=auth_header(token))
    assert list_response.status_code == 200
    assert any(r["name"] == "Room 101" for r in list_response.json())


def test_non_admin_cannot_create_room(client):
    token = register_and_login(client, "rooms-student1@example.com", role="student")
    response = client.post("/admin/rooms", json={"name": "Room 202"}, headers=auth_header(token))
    assert response.status_code == 403


def test_duplicate_room_name_rejected(client):
    token = _admin_token(client, "rooms-admin2@example.com")
    client.post("/admin/rooms", json={"name": "Room 303"}, headers=auth_header(token))
    response = client.post("/admin/rooms", json={"name": "Room 303"}, headers=auth_header(token))
    assert response.status_code == 409


def test_public_room_list_excludes_inactive(client):
    admin_token = _admin_token(client, "rooms-admin3@example.com")
    student_token = register_and_login(client, "rooms-student2@example.com", role="student")

    room_id = client.post(
        "/admin/rooms", json={"name": "Room 404"}, headers=auth_header(admin_token)
    ).json()["id"]

    visible = client.get("/rooms", headers=auth_header(student_token))
    assert any(r["id"] == room_id for r in visible.json())

    client.patch(
        f"/admin/rooms/{room_id}", json={"is_active": False}, headers=auth_header(admin_token)
    )

    hidden = client.get("/rooms", headers=auth_header(student_token))
    assert all(r["id"] != room_id for r in hidden.json())

    still_in_admin_list = client.get("/admin/rooms", headers=auth_header(admin_token))
    assert any(r["id"] == room_id for r in still_in_admin_list.json())


def test_rooms_require_authentication(client):
    assert client.get("/rooms").status_code == 401
    assert client.get("/admin/rooms").status_code == 401


def test_admin_can_create_and_list_equipment(client):
    token = _admin_token(client, "equip-admin1@example.com")
    create_response = client.post(
        "/admin/equipment",
        json={"name": "X-Ray Machine 1", "equipment_type": "xray"},
        headers=auth_header(token),
    )
    assert create_response.status_code == 201

    list_response = client.get("/admin/equipment", headers=auth_header(token))
    assert list_response.status_code == 200
    assert any(e["name"] == "X-Ray Machine 1" for e in list_response.json())


def test_non_admin_cannot_update_equipment(client):
    admin_token = _admin_token(client, "equip-admin2@example.com")
    student_token = register_and_login(client, "equip-student1@example.com", role="student")
    equipment_id = client.post(
        "/admin/equipment", json={"name": "X-Ray Machine 2"}, headers=auth_header(admin_token)
    ).json()["id"]

    response = client.patch(
        f"/admin/equipment/{equipment_id}",
        json={"is_active": False},
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


def test_public_equipment_list_excludes_inactive(client):
    admin_token = _admin_token(client, "equip-admin3@example.com")
    attending_token = register_and_login(client, "equip-attending1@example.com", role="attending")

    equipment_id = client.post(
        "/admin/equipment", json={"name": "X-Ray Machine 3"}, headers=auth_header(admin_token)
    ).json()["id"]

    visible = client.get("/equipment", headers=auth_header(attending_token))
    assert any(e["id"] == equipment_id for e in visible.json())

    client.patch(
        f"/admin/equipment/{equipment_id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )

    hidden = client.get("/equipment", headers=auth_header(attending_token))
    assert all(e["id"] != equipment_id for e in hidden.json())


def test_deactivated_room_cannot_be_booked(client):
    admin_token = _admin_token(client, "rooms-admin4@example.com")
    student_token = register_and_login(client, "rooms-student4@example.com", role="student")
    patient_id = create_patient(client, student_token)
    room_id = client.post(
        "/admin/rooms", json={"name": "Room 505"}, headers=auth_header(admin_token)
    ).json()["id"]
    client.patch(
        f"/admin/rooms/{room_id}", json={"is_active": False}, headers=auth_header(admin_token)
    )

    response = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": room_id,
            "start_time": "2026-08-10T09:00:00+00:00",
            "end_time": "2026-08-10T09:30:00+00:00",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 422


def test_deactivating_room_notifies_owning_student_via_message_and_notification(client):
    admin_token = _admin_token(client, "rooms-admin5@example.com")
    student_token = register_and_login(client, "rooms-student5@example.com", role="student")
    patient_id = create_patient(client, student_token)
    room_id = client.post(
        "/admin/rooms", json={"name": "Room 606"}, headers=auth_header(admin_token)
    ).json()["id"]

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": room_id,
            "start_time": "2026-08-11T09:00:00+00:00",
            "end_time": "2026-08-11T09:30:00+00:00",
        },
        headers=auth_header(student_token),
    ).json()
    assert appointment["status"] == "confirmed"

    deactivated = client.patch(
        f"/admin/rooms/{room_id}", json={"is_active": False}, headers=auth_header(admin_token)
    )
    assert deactivated.status_code == 200

    admin_thread = client.get("/messages/admin", headers=auth_header(student_token)).json()
    assert any("Room 606" in m["body"] for m in admin_thread)

    student_notifications = client.get("/notifications", headers=auth_header(student_token)).json()
    assert any(
        n["notification_type"] == "resource_deactivated" and "Room 606" in n["message"]
        for n in student_notifications
    )


def test_deactivating_room_with_no_future_appointments_sends_nothing(client):
    admin_token = _admin_token(client, "rooms-admin6@example.com")
    student_token = register_and_login(client, "rooms-student6@example.com", role="student")
    room_id = client.post(
        "/admin/rooms", json={"name": "Room 707"}, headers=auth_header(admin_token)
    ).json()["id"]

    client.patch(
        f"/admin/rooms/{room_id}", json={"is_active": False}, headers=auth_header(admin_token)
    )

    admin_thread = client.get("/messages/admin", headers=auth_header(student_token)).json()
    assert admin_thread == []


def test_reactivating_room_clears_scheduled_deactivation(client):
    admin_token = _admin_token(client, "rooms-admin7@example.com")
    room_id = client.post(
        "/admin/rooms", json={"name": "Room 808"}, headers=auth_header(admin_token)
    ).json()["id"]

    future = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    deactivated = client.patch(
        f"/admin/rooms/{room_id}",
        json={"is_active": False, "inactive_until": future},
        headers=auth_header(admin_token),
    )
    assert deactivated.json()["inactive_until"] is not None

    reactivated = client.patch(
        f"/admin/rooms/{room_id}", json={"is_active": True}, headers=auth_header(admin_token)
    )
    assert reactivated.json()["is_active"] is True
    assert reactivated.json()["inactive_until"] is None


def test_reactivation_job_flips_expired_scheduled_deactivations(client, db_session):
    admin_token = _admin_token(client, "rooms-admin8@example.com")
    room_id = client.post(
        "/admin/rooms", json={"name": "Room 909"}, headers=auth_header(admin_token)
    ).json()["id"]
    equipment_id = client.post(
        "/admin/equipment", json={"name": "Autoclave 909"}, headers=auth_header(admin_token)
    ).json()["id"]

    past = datetime.now(UTC) - timedelta(minutes=1)
    room_row = db_session.get(Room, room_id)
    room_row.is_active = False
    room_row.inactive_until = past
    equipment_row = db_session.get(Equipment, equipment_id)
    equipment_row.is_active = False
    equipment_row.inactive_until = past
    db_session.commit()

    reactivated = reactivate_expired_deactivations(db_session)
    assert reactivated == 2

    room_row = db_session.get(Room, room_id)
    assert room_row.is_active is True
    assert room_row.inactive_until is None
    equipment_row = db_session.get(Equipment, equipment_id)
    assert equipment_row.is_active is True
    assert equipment_row.inactive_until is None
