from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_equipment,
    create_patient,
    create_room,
    register_and_login,
)

START = "2026-09-01T09:00:00+00:00"
END = "2026-09-01T10:00:00+00:00"


def _book(
    client,
    token,
    *,
    patient_id=None,
    attending_id=None,
    room_id=None,
    equipment_id=None,
    start_time=START,
    end_time=END,
):
    body = {"start_time": start_time, "end_time": end_time}
    if patient_id is not None:
        body["patient_id"] = patient_id
    if attending_id is not None:
        body["attending_id"] = attending_id
    if room_id is not None:
        body["room_id"] = room_id
    if equipment_id is not None:
        body["equipment_id"] = equipment_id
    return client.post("/appointments", json=body, headers=auth_header(token))


def _wait(
    client,
    token,
    *,
    patient_id=None,
    attending_id=None,
    room_id=None,
    equipment_id=None,
    start_time=START,
    end_time=END,
):
    body = {"start_time": start_time, "end_time": end_time}
    if patient_id is not None:
        body["patient_id"] = patient_id
    if attending_id is not None:
        body["attending_id"] = attending_id
    if room_id is not None:
        body["room_id"] = room_id
    if equipment_id is not None:
        body["equipment_id"] = equipment_id
    return client.post("/waitlist", json=body, headers=auth_header(token))


def test_student_creates_waitlist_entry(client):
    student_token = register_and_login(client, "wl-s1@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = _wait(client, student_token, patient_id=patient_id)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert body["notified_at"] is None


def test_patient_creates_waitlist_entry(client):
    student_token = register_and_login(client, "wl-s2@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "wl-p2@example.com")

    response = _wait(client, patient_token)
    assert response.status_code == 201
    assert response.json()["status"] == "active"


def test_create_rejects_invalid_attending_role(client):
    student_token = register_and_login(client, "wl-s3@example.com", role="student")
    other_student_token = register_and_login(client, "wl-s3b@example.com", role="student")
    not_attending_id = client.get("/users/me", headers=auth_header(other_student_token)).json()[
        "id"
    ]
    patient_id = create_patient(client, student_token)

    response = _wait(client, student_token, patient_id=patient_id, attending_id=not_attending_id)
    assert response.status_code == 422


def test_invalid_time_range_rejected(client):
    student_token = register_and_login(client, "wl-s4@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = _wait(client, student_token, patient_id=patient_id, start_time=END, end_time=START)
    assert response.status_code == 422


def test_visibility_scoping(client):
    student_token = register_and_login(client, "wl-s5@example.com", role="student")
    other_student_token = register_and_login(client, "wl-s5b@example.com", role="student")
    attending_token = register_and_login(client, "wl-a5@example.com", role="attending")
    admin_token = register_and_login(client, "wl-admin5@example.com", role="admin")
    patient_id = create_patient(client, student_token)

    entry = _wait(client, student_token, patient_id=patient_id).json()

    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)).status_code
        == 404
    )
    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(attending_token)).status_code
        == 404
    )
    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(student_token)).status_code
        == 200
    )
    assert (
        client.get(f"/waitlist/{entry['id']}", headers=auth_header(admin_token)).status_code == 200
    )

    listing = client.get("/waitlist", headers=auth_header(other_student_token)).json()
    assert all(e["id"] != entry["id"] for e in listing)


def test_cancel_by_owning_student(client):
    student_token = register_and_login(client, "wl-s6@example.com", role="student")
    patient_id = create_patient(client, student_token)
    entry = _wait(client, student_token, patient_id=patient_id).json()

    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(student_token))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_by_self_patient(client):
    student_token = register_and_login(client, "wl-s7@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "wl-p7@example.com")
    entry = _wait(client, patient_token).json()

    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(patient_token))
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_cancel_already_cancelled_conflicts(client):
    student_token = register_and_login(client, "wl-s8@example.com", role="student")
    patient_id = create_patient(client, student_token)
    entry = _wait(client, student_token, patient_id=patient_id).json()

    client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(student_token))
    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(student_token))
    assert response.status_code == 409


def test_admin_cannot_cancel_others_entry(client):
    student_token = register_and_login(client, "wl-s9@example.com", role="student")
    admin_token = register_and_login(client, "wl-admin9@example.com", role="admin")
    patient_id = create_patient(client, student_token)
    entry = _wait(client, student_token, patient_id=patient_id).json()

    response = client.post(f"/waitlist/{entry['id']}/cancel", headers=auth_header(admin_token))
    assert response.status_code == 403


def test_waitlist_requires_authentication(client):
    assert client.get("/waitlist").status_code == 401
    assert client.post("/waitlist", json={}).status_code == 401


def test_cancellation_triggers_waitlist_match(client):
    student_token = register_and_login(client, "wl-s10@example.com", role="student")
    attending_token = register_and_login(client, "wl-a10@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]

    other_student_token = register_and_login(client, "wl-s10b@example.com", role="student")
    _, waiting_patient_token = create_and_login_patient(
        client, other_student_token, "wl-p10b@example.com"
    )
    waiting_patient_id = client.get("/users/me", headers=auth_header(waiting_patient_token)).json()[
        "id"
    ]

    entry = _wait(
        client, other_student_token, patient_id=waiting_patient_id, attending_id=attending_id
    ).json()
    assert entry["status"] == "active"

    patient_id = create_patient(client, student_token)
    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()

    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "notified"
    assert updated_entry["notified_at"] is not None

    student_notifications = client.get(
        "/notifications", headers=auth_header(other_student_token)
    ).json()
    assert any(n["notification_type"] == "waitlist_slot_available" for n in student_notifications)

    patient_notifications = client.get(
        "/notifications", headers=auth_header(waiting_patient_token)
    ).json()
    assert any(n["notification_type"] == "waitlist_slot_available" for n in patient_notifications)


def test_reject_also_triggers_waitlist_match(client):
    student_token = register_and_login(client, "wl-s11@example.com", role="student")
    attending_token = register_and_login(client, "wl-a11@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]

    other_student_token = register_and_login(client, "wl-s11b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)
    entry = _wait(
        client, other_student_token, patient_id=other_patient_id, attending_id=attending_id
    ).json()

    patient_id = create_patient(client, student_token)
    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()

    client.post(f"/appointments/{appointment['id']}/reject", headers=auth_header(attending_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "notified"


def test_generic_waitlist_entry_never_matches(client):
    student_token = register_and_login(client, "wl-s12@example.com", role="student")
    attending_token = register_and_login(client, "wl-a12@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]

    other_student_token = register_and_login(client, "wl-s12b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)
    entry = _wait(client, other_student_token, patient_id=other_patient_id).json()

    patient_id = create_patient(client, student_token)
    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()
    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "active"


def test_cancellation_without_shared_resource_does_not_match(client):
    student_token = register_and_login(client, "wl-s13@example.com", role="student")
    admin_token = register_and_login(client, "wl-admin13@example.com", role="admin")
    room_id = create_room(client, admin_token, "WL Room 13")

    other_student_token = register_and_login(client, "wl-s13b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)
    entry = _wait(client, other_student_token, patient_id=other_patient_id, room_id=room_id).json()

    patient_id = create_patient(client, student_token)
    appointment = _book(client, student_token, patient_id=patient_id).json()
    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "active"


def test_mismatched_room_does_not_match(client):
    student_token = register_and_login(client, "wl-s14@example.com", role="student")
    admin_token = register_and_login(client, "wl-admin14@example.com", role="admin")
    room_a = create_room(client, admin_token, "WL Room A")
    room_b = create_room(client, admin_token, "WL Room B")

    other_student_token = register_and_login(client, "wl-s14b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)
    entry = _wait(client, other_student_token, patient_id=other_patient_id, room_id=room_a).json()

    patient_id = create_patient(client, student_token)
    appointment = _book(client, student_token, patient_id=patient_id, room_id=room_b).json()
    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "active"


def test_non_overlapping_time_does_not_match(client):
    student_token = register_and_login(client, "wl-s15@example.com", role="student")
    admin_token = register_and_login(client, "wl-admin15@example.com", role="admin")
    equipment_id = create_equipment(client, admin_token, "WL Equipment 15")

    other_student_token = register_and_login(client, "wl-s15b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)
    entry = _wait(
        client,
        other_student_token,
        patient_id=other_patient_id,
        equipment_id=equipment_id,
        start_time="2026-09-02T09:00:00+00:00",
        end_time="2026-09-02T10:00:00+00:00",
    ).json()

    patient_id = create_patient(client, student_token)
    appointment = _book(
        client, student_token, patient_id=patient_id, equipment_id=equipment_id
    ).json()
    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    updated_entry = client.get(
        f"/waitlist/{entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "active"
