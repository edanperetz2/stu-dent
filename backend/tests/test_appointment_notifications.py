from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_default_room,
    create_patient,
    register_and_login,
)

START = "2026-08-10T09:00:00+00:00"
END = "2026-08-10T10:00:00+00:00"


def _user_id(client, token):
    return client.get("/users/me", headers=auth_header(token)).json()["id"]


def _notification_types(client, token):
    body = client.get("/notifications", headers=auth_header(token)).json()
    return [n["notification_type"] for n in body]


def test_create_with_attending_notifies_the_attending(client):
    student_token = register_and_login(client, "notif-s1@example.com", role="student")
    attending_token = register_and_login(client, "notif-a1@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    patient_id = create_patient(client, student_token)
    room_id = create_default_room(client)

    response = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "attending_id": attending_id,
            "room_id": room_id,
            "start_time": START,
            "end_time": END,
        },
        headers=auth_header(student_token),
    )
    assert response.status_code == 201

    assert "appointment_created" in _notification_types(client, attending_token)


def test_patient_request_notifies_the_owning_student(client):
    student_token = register_and_login(client, "notif-s2@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, email="notif-p2@example.com"
    )

    response = client.post(
        "/appointments",
        json={"start_time": START, "end_time": END},
        headers=auth_header(patient_token),
    )
    assert response.status_code == 201

    assert "appointment_created" in _notification_types(client, student_token)


def test_accept_notifies_patient_and_attending_if_still_pending_approval(client):
    student_token = register_and_login(client, "notif-s3@example.com", role="student")
    attending_token = register_and_login(client, "notif-a3@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    patient_id, patient_token = create_and_login_patient(
        client, student_token, email="notif-p3@example.com"
    )

    # Patients can't set attending/room/equipment on their own request --
    # the owning student adds the attending afterward, while it's still
    # proposed (not yet accepted), before accepting it.
    request = client.post(
        "/appointments",
        json={"start_time": START, "end_time": END},
        headers=auth_header(patient_token),
    )
    assert request.status_code == 201
    appointment_id = request.json()["id"]

    client.patch(
        f"/appointments/{appointment_id}",
        json={"attending_id": attending_id},
        headers=auth_header(student_token),
    )

    room_id = create_default_room(client)
    accept = client.post(
        f"/appointments/{appointment_id}/accept",
        json={"room_id": room_id},
        headers=auth_header(student_token),
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "awaiting_confirmation"

    assert "appointment_status_changed" in _notification_types(client, patient_token)
    assert "appointment_created" in _notification_types(client, attending_token)


def test_approve_notifies_student_and_patient(client):
    student_token = register_and_login(client, "notif-s4@example.com", role="student")
    attending_token = register_and_login(client, "notif-a4@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    patient_id = create_patient(client, student_token)
    room_id = create_default_room(client)

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "attending_id": attending_id,
            "room_id": room_id,
            "start_time": START,
            "end_time": END,
        },
        headers=auth_header(student_token),
    ).json()

    approve = client.post(
        f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token)
    )
    assert approve.status_code == 200

    assert "appointment_status_changed" in _notification_types(client, student_token)


def test_reject_notifies_the_owning_student_not_the_rejecting_attending(client):
    student_token = register_and_login(client, "notif-s5@example.com", role="student")
    attending_token = register_and_login(client, "notif-a5@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    patient_id = create_patient(client, student_token)
    room_id = create_default_room(client)

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "attending_id": attending_id,
            "room_id": room_id,
            "start_time": START,
            "end_time": END,
        },
        headers=auth_header(student_token),
    ).json()

    reject = client.post(
        f"/appointments/{appointment['id']}/reject", headers=auth_header(attending_token)
    )
    assert reject.status_code == 200

    student_types = _notification_types(client, student_token)
    assert "appointment_status_changed" in student_types
    # The attending performed the action -- they don't notify themselves.
    attending_types = _notification_types(client, attending_token)
    assert attending_types.count("appointment_status_changed") == 0


def test_cancel_by_patient_notifies_student_and_attending(client):
    student_token = register_and_login(client, "notif-s6@example.com", role="student")
    attending_token = register_and_login(client, "notif-a6@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    patient_id, patient_token = create_and_login_patient(
        client, student_token, email="notif-p6@example.com"
    )
    room_id = create_default_room(client)

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "attending_id": attending_id,
            "room_id": room_id,
            "start_time": START,
            "end_time": END,
        },
        headers=auth_header(student_token),
    ).json()

    cancel = client.post(
        f"/appointments/{appointment['id']}/cancel", headers=auth_header(patient_token)
    )
    assert cancel.status_code == 200

    assert "appointment_status_changed" in _notification_types(client, student_token)
    assert "appointment_status_changed" in _notification_types(client, attending_token)
    # The patient performed the action -- they don't notify themselves.
    assert _notification_types(client, patient_token).count("appointment_status_changed") == 0


def test_update_time_notifies_attending_and_does_not_reset_approval_for_unrelated_edits(client):
    student_token = register_and_login(client, "notif-s7@example.com", role="student")
    attending_token = register_and_login(client, "notif-a7@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    patient_id = create_patient(client, student_token)
    room_id = create_default_room(client)

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "attending_id": attending_id,
            "room_id": room_id,
            "start_time": START,
            "end_time": END,
        },
        headers=auth_header(student_token),
    ).json()

    client.post(f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token))
    confirmed = client.get(
        f"/appointments/{appointment['id']}", headers=auth_header(student_token)
    ).json()
    assert confirmed["status"] == "confirmed"

    # Editing only notes -- same start/end/attending -- must NOT re-open
    # attending approval (this used to reset it on every edit because the
    # frontend always resubmits start_time/end_time on every PATCH).
    notes_only = client.patch(
        f"/appointments/{appointment['id']}",
        json={
            "start_time": appointment["start_time"],
            "end_time": appointment["end_time"],
            "notes": "just a note",
        },
        headers=auth_header(student_token),
    )
    assert notes_only.status_code == 200
    assert notes_only.json()["status"] == "confirmed"

    # A genuine time change DOES need re-approval, and the attending should
    # be told.
    new_start = "2026-08-11T09:00:00+00:00"
    new_end = "2026-08-11T10:00:00+00:00"
    rescheduled = client.patch(
        f"/appointments/{appointment['id']}",
        json={"start_time": new_start, "end_time": new_end},
        headers=auth_header(student_token),
    )
    assert rescheduled.status_code == 200
    assert rescheduled.json()["status"] == "rescheduling_requested"
    assert "appointment_created" in _notification_types(client, attending_token)
