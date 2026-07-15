from datetime import UTC, datetime, timedelta

from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_default_room,
    create_equipment,
    create_patient,
    create_room,
    register_and_login,
)

START = "2026-08-01T09:00:00+00:00"
END = "2026-08-01T10:00:00+00:00"


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
    notes=None,
):
    body = {"start_time": start_time, "end_time": end_time}
    if patient_id is not None:
        body["patient_id"] = patient_id
        if room_id is None:
            room_id = create_default_room(client)
    if attending_id is not None:
        body["attending_id"] = attending_id
    if room_id is not None:
        body["room_id"] = room_id
    if equipment_id is not None:
        body["equipment_id"] = equipment_id
    if notes is not None:
        body["notes"] = notes
    return client.post("/appointments", json=body, headers=auth_header(token))


def test_student_creates_appointment_no_attending_confirms_immediately(client):
    student_token = register_and_login(client, "s1@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = _book(client, student_token, patient_id=patient_id)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["student_confirmed_at"] is not None
    assert body["attending_approved_at"] is None


def test_student_creates_appointment_with_attending_awaits_approval(client):
    student_token = register_and_login(client, "s2@example.com", role="student")
    attending_token = register_and_login(client, "a2@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    response = _book(client, student_token, patient_id=patient_id, attending_id=attending_id)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "awaiting_confirmation"
    assert body["student_confirmed_at"] is not None
    assert body["attending_approved_at"] is None


def test_attending_approves_moves_to_confirmed(client):
    student_token = register_and_login(client, "s3@example.com", role="student")
    attending_token = register_and_login(client, "a3@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()
    assert appointment["status"] == "awaiting_confirmation"

    response = client.post(
        f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["attending_approved_at"] is not None


def test_patient_creates_appointment_is_proposed(client):
    student_token = register_and_login(client, "s4@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "p4@example.com")

    response = _book(client, patient_token)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "proposed"
    assert body["student_confirmed_at"] is None


def test_patient_cannot_set_attending_room_equipment(client):
    student_token = register_and_login(client, "s5@example.com", role="student")
    admin_token = register_and_login(client, "admin5@example.com", role="admin")
    _, patient_token = create_and_login_patient(client, student_token, "p5@example.com")
    room_id = create_room(client, admin_token, "Room 5")

    response = _book(client, patient_token, room_id=room_id)
    assert response.status_code == 422


def test_student_accepts_proposed_patient_request(client):
    student_token = register_and_login(client, "s6@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "p6@example.com")

    appointment = _book(client, patient_token).json()
    assert appointment["status"] == "proposed"
    assert appointment["room_id"] is None

    room_id = create_default_room(client)
    response = client.post(
        f"/appointments/{appointment['id']}/accept",
        json={"room_id": room_id},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert response.json()["room_id"] == room_id


def test_accept_without_a_room_is_rejected(client):
    student_token = register_and_login(client, "s6b@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "p6b@example.com")

    appointment = _book(client, patient_token).json()

    response = client.post(
        f"/appointments/{appointment['id']}/accept", headers=auth_header(student_token)
    )
    assert response.status_code == 422


def test_accept_twice_conflicts(client):
    student_token = register_and_login(client, "s7@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "p7@example.com")
    appointment = _book(client, patient_token).json()
    room_id = create_default_room(client)

    first = client.post(
        f"/appointments/{appointment['id']}/accept",
        json={"room_id": room_id},
        headers=auth_header(student_token),
    )
    assert first.status_code == 200
    second = client.post(
        f"/appointments/{appointment['id']}/accept",
        json={"room_id": room_id},
        headers=auth_header(student_token),
    )
    assert second.status_code == 409


def test_invalid_time_range_rejected(client):
    student_token = register_and_login(client, "s8@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = _book(client, student_token, patient_id=patient_id, start_time=END, end_time=START)
    assert response.status_code == 422


def test_create_rejects_invalid_attending_role(client):
    student_token = register_and_login(client, "s9@example.com", role="student")
    other_student_token = register_and_login(client, "s9b@example.com", role="student")
    not_attending_id = client.get("/users/me", headers=auth_header(other_student_token)).json()[
        "id"
    ]
    patient_id = create_patient(client, student_token)

    response = _book(client, student_token, patient_id=patient_id, attending_id=not_attending_id)
    assert response.status_code == 422


def test_create_rejects_inactive_room(client):
    student_token = register_and_login(client, "s10@example.com", role="student")
    admin_token = register_and_login(client, "admin10@example.com", role="admin")
    patient_id = create_patient(client, student_token)
    room_id = create_room(client, admin_token, "Room 10")
    client.patch(
        f"/admin/rooms/{room_id}", json={"is_active": False}, headers=auth_header(admin_token)
    )

    response = _book(client, student_token, patient_id=patient_id, room_id=room_id)
    assert response.status_code == 422


def test_create_rejects_patient_not_owned_by_student(client):
    student_token = register_and_login(client, "s11@example.com", role="student")
    other_student_token = register_and_login(client, "s11b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)

    response = _book(client, student_token, patient_id=other_patient_id)
    assert response.status_code == 422


def test_update_cannot_clear_room_id(client):
    student_token = register_and_login(client, "s11c@example.com", role="student")
    patient_id = create_patient(client, student_token)
    appointment = _book(client, student_token, patient_id=patient_id).json()

    response = client.patch(
        f"/appointments/{appointment['id']}",
        json={"room_id": None},
        headers=auth_header(student_token),
    )
    assert response.status_code == 422


def test_student_can_assign_room_to_pending_patient_request_before_accepting(client):
    student_token = register_and_login(client, "s11d@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "p11d@example.com")
    appointment = _book(client, patient_token).json()
    room_id = create_default_room(client)

    patched = client.patch(
        f"/appointments/{appointment['id']}",
        json={"room_id": room_id},
        headers=auth_header(student_token),
    )
    assert patched.status_code == 200
    assert patched.json()["room_id"] == room_id
    assert patched.json()["status"] == "proposed"

    accepted = client.post(
        f"/appointments/{appointment['id']}/accept", headers=auth_header(student_token)
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "confirmed"
    assert accepted.json()["room_id"] == room_id


def test_reassigning_attending_without_time_change_is_awaiting_confirmation(client):
    student_token = register_and_login(client, "s12@example.com", role="student")
    attending_token = register_and_login(client, "a12@example.com", role="attending")
    other_attending_token = register_and_login(client, "a12b@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    other_attending_id = client.get("/users/me", headers=auth_header(other_attending_token)).json()[
        "id"
    ]
    patient_id = create_patient(client, student_token)

    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()
    client.post(f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token))

    response = client.patch(
        f"/appointments/{appointment['id']}",
        json={"attending_id": other_attending_id},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "awaiting_confirmation"
    assert body["attending_approved_at"] is None


def test_changing_time_on_confirmed_with_attending_is_rescheduling_requested(client):
    student_token = register_and_login(client, "s13@example.com", role="student")
    attending_token = register_and_login(client, "a13@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()
    client.post(f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token))

    new_start = "2026-08-01T11:00:00+00:00"
    new_end = "2026-08-01T12:00:00+00:00"
    response = client.patch(
        f"/appointments/{appointment['id']}",
        json={"start_time": new_start, "end_time": new_end},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rescheduling_requested"
    assert body["attending_approved_at"] is None

    approve_response = client.post(
        f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token)
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "confirmed"


def test_reject_by_student_and_by_attending(client):
    student_token = register_and_login(client, "s14@example.com", role="student")
    attending_token = register_and_login(client, "a14@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    appt_a = _book(client, student_token, patient_id=patient_id).json()
    reject_by_student = client.post(
        f"/appointments/{appt_a['id']}/reject", headers=auth_header(student_token)
    )
    assert reject_by_student.status_code == 200
    assert reject_by_student.json()["status"] == "cancelled"

    appt_b = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        start_time="2026-08-02T09:00:00+00:00",
        end_time="2026-08-02T10:00:00+00:00",
    ).json()
    reject_by_attending = client.post(
        f"/appointments/{appt_b['id']}/reject", headers=auth_header(attending_token)
    )
    assert reject_by_attending.status_code == 200
    assert reject_by_attending.json()["status"] == "cancelled"


def test_cancel_by_patient_and_by_student(client):
    student_token = register_and_login(client, "s15@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "p15@example.com")

    appt_a = _book(client, patient_token).json()
    cancel_by_patient = client.post(
        f"/appointments/{appt_a['id']}/cancel", headers=auth_header(patient_token)
    )
    assert cancel_by_patient.status_code == 200
    assert cancel_by_patient.json()["status"] == "cancelled"

    patient_id = create_patient(client, student_token, full_name="Second Patient")
    appt_b = _book(
        client,
        student_token,
        patient_id=patient_id,
        start_time="2026-08-03T09:00:00+00:00",
        end_time="2026-08-03T10:00:00+00:00",
    ).json()
    cancel_by_student = client.post(
        f"/appointments/{appt_b['id']}/cancel", headers=auth_header(student_token)
    )
    assert cancel_by_student.status_code == 200
    assert cancel_by_student.json()["status"] == "cancelled"


def test_complete_and_no_show_require_confirmed_status(client):
    student_token = register_and_login(client, "s16@example.com", role="student")
    patient_id = create_patient(client, student_token)

    # Must already be in the past -- complete/no-show are gated on the
    # appointment's start time, see test_complete_and_no_show_require_started_time.
    proposed_like = _book(
        client,
        student_token,
        patient_id=patient_id,
        start_time="2020-08-04T09:00:00+00:00",
        end_time="2020-08-04T10:00:00+00:00",
    ).json()
    # already confirmed since no attending; complete should succeed
    complete_response = client.post(
        f"/appointments/{proposed_like['id']}/complete", headers=auth_header(student_token)
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    # completing again fails (already terminal)
    complete_again = client.post(
        f"/appointments/{proposed_like['id']}/complete", headers=auth_header(student_token)
    )
    assert complete_again.status_code == 409

    no_show_appt = _book(
        client,
        student_token,
        patient_id=patient_id,
        start_time="2020-08-05T09:00:00+00:00",
        end_time="2020-08-05T10:00:00+00:00",
    ).json()
    no_show_response = client.post(
        f"/appointments/{no_show_appt['id']}/no-show", headers=auth_header(student_token)
    )
    assert no_show_response.status_code == 200
    assert no_show_response.json()["status"] == "no_show"


def test_complete_and_no_show_require_started_time(client):
    student_token = register_and_login(client, "s16b@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    future_appt = _book(
        client,
        student_token,
        patient_id=patient_id,
        start_time=(now + timedelta(hours=1)).isoformat(),
        end_time=(now + timedelta(hours=2)).isoformat(),
    ).json()
    assert future_appt["status"] == "confirmed"

    complete_response = client.post(
        f"/appointments/{future_appt['id']}/complete", headers=auth_header(student_token)
    )
    assert complete_response.status_code == 409

    no_show_response = client.post(
        f"/appointments/{future_appt['id']}/no-show", headers=auth_header(student_token)
    )
    assert no_show_response.status_code == 409

    # cancel is unaffected by time -- must stay available for a future (and,
    # by the same logic, a past) appointment.
    cancel_response = client.post(
        f"/appointments/{future_appt['id']}/cancel", headers=auth_header(student_token)
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_visibility_scoping_returns_404_out_of_scope(client):
    student_token = register_and_login(client, "s17@example.com", role="student")
    other_student_token = register_and_login(client, "s17b@example.com", role="student")
    attending_token = register_and_login(client, "a17@example.com", role="attending")
    _, patient_token = create_and_login_patient(client, student_token, "p17@example.com")
    _, other_patient_token = create_and_login_patient(
        client, other_student_token, "p17b@example.com"
    )
    patient_id = create_patient(client, student_token, full_name="Visible Patient")

    appointment = _book(client, student_token, patient_id=patient_id).json()

    assert (
        client.get(
            f"/appointments/{appointment['id']}", headers=auth_header(other_student_token)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/appointments/{appointment['id']}", headers=auth_header(attending_token)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/appointments/{appointment['id']}", headers=auth_header(other_patient_token)
        ).status_code
        == 404
    )

    own_view = client.get(f"/appointments/{appointment['id']}", headers=auth_header(student_token))
    assert own_view.status_code == 200


def test_admin_can_view_all_appointments(client):
    student_token = register_and_login(client, "s18@example.com", role="student")
    admin_token = register_and_login(client, "admin18@example.com", role="admin")
    patient_id = create_patient(client, student_token)

    appointment = _book(client, student_token, patient_id=patient_id).json()

    response = client.get(f"/appointments/{appointment['id']}", headers=auth_header(admin_token))
    assert response.status_code == 200

    list_response = client.get("/appointments", headers=auth_header(admin_token))
    assert any(a["id"] == appointment["id"] for a in list_response.json())


def test_equipment_reference_validated(client):
    student_token = register_and_login(client, "s19@example.com", role="student")
    admin_token = register_and_login(client, "admin19@example.com", role="admin")
    patient_id = create_patient(client, student_token)

    unknown_id = "00000000-0000-0000-0000-000000000000"
    rejected = _book(client, student_token, patient_id=patient_id, equipment_id=unknown_id)
    assert rejected.status_code == 422

    equipment_id = create_equipment(client, admin_token, "X-Ray 19")
    accepted = _book(client, student_token, patient_id=patient_id, equipment_id=equipment_id)
    assert accepted.status_code == 201
    assert accepted.json()["equipment_id"] == equipment_id


def test_response_includes_denormalized_participant_and_room_names(client):
    student_token = register_and_login(
        client, "s20@example.com", role="student", full_name="Stu Dent"
    )
    attending_token = register_and_login(
        client, "a20@example.com", role="attending", full_name="Dr. Attend"
    )
    admin_token = register_and_login(client, "admin20@example.com", role="admin")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token, full_name="Pat Ient")
    room_id = create_room(client, admin_token, "Room 20")
    equipment_id = create_equipment(client, admin_token, "Autoclave 20")

    response = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        room_id=room_id,
        equipment_id=equipment_id,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["student_name"] == "Stu Dent"
    assert body["patient_name"] == "Pat Ient"
    assert body["attending_name"] == "Dr. Attend"
    assert body["room_name"] == "Room 20"
    assert body["equipment_name"] == "Autoclave 20"

    listed = client.get("/appointments", headers=auth_header(student_token)).json()
    booked = next(a for a in listed if a["id"] == body["id"])
    assert booked["room_name"] == "Room 20"
    assert booked["equipment_name"] == "Autoclave 20"
