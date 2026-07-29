from datetime import UTC, datetime, timedelta

from app.jobs.reactivation import reactivate_expired_deactivations
from app.models.equipment import Equipment
from app.models.room import Room
from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_default_room,
    create_patient,
    register_and_login,
)


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


def test_deactivated_equipment_cannot_be_booked(client):
    admin_token = _admin_token(client, "equip-admin4@example.com")
    student_token = register_and_login(client, "equip-student4@example.com", role="student")
    patient_id = create_patient(client, student_token)
    room_id = create_default_room(client)
    equipment_id = client.post(
        "/admin/equipment", json={"name": "Autoclave 505"}, headers=auth_header(admin_token)
    ).json()["id"]
    client.patch(
        f"/admin/equipment/{equipment_id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )

    response = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": room_id,
            "equipment_id": equipment_id,
            "start_time": "2026-08-10T09:00:00+00:00",
            "end_time": "2026-08-10T09:30:00+00:00",
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 422


def test_deactivating_equipment_notifies_owning_student_via_message_and_notification(client):
    admin_token = _admin_token(client, "equip-admin5@example.com")
    student_token = register_and_login(client, "equip-student5@example.com", role="student")
    patient_id = create_patient(client, student_token)
    room_id = create_default_room(client)
    equipment_id = client.post(
        "/admin/equipment", json={"name": "Autoclave 606"}, headers=auth_header(admin_token)
    ).json()["id"]

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": room_id,
            "equipment_id": equipment_id,
            "start_time": "2026-08-11T09:00:00+00:00",
            "end_time": "2026-08-11T09:30:00+00:00",
        },
        headers=auth_header(student_token),
    ).json()
    assert appointment["status"] == "confirmed"

    deactivated = client.patch(
        f"/admin/equipment/{equipment_id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )
    assert deactivated.status_code == 200

    admin_thread = client.get("/messages/admin", headers=auth_header(student_token)).json()
    assert any("Autoclave 606" in m["body"] for m in admin_thread)

    student_notifications = client.get("/notifications", headers=auth_header(student_token)).json()
    assert any(
        n["notification_type"] == "resource_deactivated" and "Autoclave 606" in n["message"]
        for n in student_notifications
    )


def test_deactivating_equipment_with_no_future_appointments_sends_nothing(client):
    admin_token = _admin_token(client, "equip-admin6@example.com")
    student_token = register_and_login(client, "equip-student6@example.com", role="student")
    equipment_id = client.post(
        "/admin/equipment", json={"name": "Autoclave 707"}, headers=auth_header(admin_token)
    ).json()["id"]

    client.patch(
        f"/admin/equipment/{equipment_id}",
        json={"is_active": False},
        headers=auth_header(admin_token),
    )

    admin_thread = client.get("/messages/admin", headers=auth_header(student_token)).json()
    assert admin_thread == []


def test_resources_schedule_reveals_booking_student_but_not_patient(client):
    admin_token = _admin_token(client, "rooms-admin9@example.com")
    student_token = register_and_login(
        client, "rooms-student9@example.com", role="student", full_name="Booking Student"
    )
    patient_id = create_patient(client, student_token, full_name="Confidential Patient")
    room_id = client.post(
        "/admin/rooms", json={"name": "Room 1010"}, headers=auth_header(admin_token)
    ).json()["id"]
    equipment_id = client.post(
        "/admin/equipment", json={"name": "Autoclave 1010"}, headers=auth_header(admin_token)
    ).json()["id"]

    booked = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": room_id,
            "equipment_id": equipment_id,
            "start_time": "2026-08-12T09:00:00+00:00",
            "end_time": "2026-08-12T09:30:00+00:00",
        },
        headers=auth_header(student_token),
    ).json()
    assert booked["status"] == "confirmed"

    # Any authenticated role -- not just the booking student -- can see the
    # combined feed, learn which student booked each slot, but never the
    # patient or any other appointment detail.
    other_student_token = register_and_login(client, "rooms-student10@example.com", role="student")
    schedule = client.get("/resources/schedule", headers=auth_header(other_student_token))
    assert schedule.status_code == 200
    body = schedule.json()

    room_entries = [
        row for row in body if row["resource_kind"] == "room" and row["resource_id"] == room_id
    ]
    assert len(room_entries) == 1
    assert room_entries[0]["resource_name"] == "Room 1010"
    assert room_entries[0]["student_name"] == "Booking Student"
    assert room_entries[0]["start_time"] == booked["start_time"]
    assert room_entries[0]["end_time"] == booked["end_time"]
    assert set(room_entries[0].keys()) == {
        "resource_kind",
        "resource_id",
        "resource_name",
        "start_time",
        "end_time",
        "student_name",
    }

    equipment_entries = [
        row
        for row in body
        if row["resource_kind"] == "equipment" and row["resource_id"] == equipment_id
    ]
    assert len(equipment_entries) == 1
    assert equipment_entries[0]["resource_name"] == "Autoclave 1010"
    assert equipment_entries[0]["student_name"] == "Booking Student"

    assert "Confidential Patient" not in schedule.text


def test_resources_schedule_scopes_patient_to_own_bookings(client):
    admin_token = _admin_token(client, "rooms-admin11@example.com")
    student_token = register_and_login(client, "rooms-student12@example.com", role="student")
    other_student_token = register_and_login(client, "rooms-student13@example.com", role="student")

    patient_id, patient_token = create_and_login_patient(
        client, student_token, email="rooms-patient12@example.com"
    )
    other_patient_id, _ = create_and_login_patient(
        client, other_student_token, email="rooms-patient13@example.com"
    )

    room_id = client.post(
        "/admin/rooms", json={"name": "Room 1111"}, headers=auth_header(admin_token)
    ).json()["id"]
    other_room_id = client.post(
        "/admin/rooms", json={"name": "Room 1112"}, headers=auth_header(admin_token)
    ).json()["id"]

    own_booking = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": room_id,
            "start_time": "2026-09-01T09:00:00+00:00",
            "end_time": "2026-09-01T09:30:00+00:00",
        },
        headers=auth_header(student_token),
    ).json()
    assert own_booking["status"] == "confirmed"

    other_booking = client.post(
        "/appointments",
        json={
            "patient_id": other_patient_id,
            "room_id": other_room_id,
            "start_time": "2026-09-01T10:00:00+00:00",
            "end_time": "2026-09-01T10:30:00+00:00",
        },
        headers=auth_header(other_student_token),
    ).json()
    assert other_booking["status"] == "confirmed"

    schedule = client.get("/resources/schedule", headers=auth_header(patient_token))
    assert schedule.status_code == 200
    body = schedule.json()

    resource_ids = {row["resource_id"] for row in body}
    assert room_id in resource_ids
    assert other_room_id not in resource_ids


def test_resources_schedule_excludes_cancelled_and_proposed(client):
    admin_token = _admin_token(client, "rooms-admin10@example.com")
    student_token = register_and_login(client, "rooms-student11@example.com", role="student")
    patient_id = create_patient(client, student_token)
    room_id = client.post(
        "/admin/rooms", json={"name": "Room 1111"}, headers=auth_header(admin_token)
    ).json()["id"]

    cancelled = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": room_id,
            "start_time": "2026-08-13T09:00:00+00:00",
            "end_time": "2026-08-13T09:30:00+00:00",
        },
        headers=auth_header(student_token),
    ).json()
    client.post(f"/appointments/{cancelled['id']}/cancel", headers=auth_header(student_token))

    schedule = client.get("/resources/schedule", headers=auth_header(student_token))
    assert all(row["resource_id"] != room_id for row in schedule.json())


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
