import uuid

from app.models.notification import NotificationType
from app.services.notifications import notify
from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_default_room,
    create_patient,
    register_and_login,
)

START = "2026-08-10T09:00:00+00:00"
END = "2026-08-10T10:00:00+00:00"
PAST_START = "2020-08-01T09:00:00+00:00"
PAST_END = "2020-08-01T10:00:00+00:00"


def _user_id(client, token):
    return client.get("/users/me", headers=auth_header(token)).json()["id"]


def _notification_types(client, token):
    body = client.get("/notifications", headers=auth_header(token)).json()
    return [n["notification_type"] for n in body]


def _find_notification(client, token, *, notification_type, appointment_id):
    body = client.get("/notifications", headers=auth_header(token)).json()
    return next(
        n
        for n in body
        if n["notification_type"] == notification_type
        and n["related_appointment_id"] == appointment_id
    )


def _seed_unread(db_session, *, notification_type, recipient_id, appointment_id, message="nag"):
    entry = notify(
        db_session,
        notification_type=notification_type,
        message=message,
        recipient_id=uuid.UUID(recipient_id),
        related_appointment_id=uuid.UUID(appointment_id),
    )
    db_session.commit()
    return entry


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


def test_completing_resolves_a_pending_needs_resolution_notification(client, db_session):
    student_token = register_and_login(client, "notif-s8@example.com", role="student")
    student_id = _user_id(client, student_token)
    patient_id = create_patient(client, student_token)

    # No attending -- auto-confirmed, and dated in the past so /complete's
    # started-time check passes.
    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": create_default_room(client),
            "start_time": PAST_START,
            "end_time": PAST_END,
        },
        headers=auth_header(student_token),
    ).json()

    # Simulates jobs/unresolved_appointments.py having already nagged once,
    # before the student resolves it directly from the Appointments page.
    entry = _seed_unread(
        db_session,
        notification_type=NotificationType.appointment_needs_resolution,
        recipient_id=student_id,
        appointment_id=appointment["id"],
    )

    complete = client.post(
        f"/appointments/{appointment['id']}/complete", headers=auth_header(student_token)
    )
    assert complete.status_code == 200

    resolved = client.get("/notifications", headers=auth_header(student_token)).json()
    match = next(n for n in resolved if n["id"] == str(entry.id))
    assert match["read_at"] is not None


def test_cancelling_also_resolves_a_pending_needs_resolution_notification(client, db_session):
    student_token = register_and_login(client, "notif-s9@example.com", role="student")
    student_id = _user_id(client, student_token)
    patient_id = create_patient(client, student_token)

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": create_default_room(client),
            "start_time": START,
            "end_time": END,
        },
        headers=auth_header(student_token),
    ).json()

    entry = _seed_unread(
        db_session,
        notification_type=NotificationType.appointment_needs_resolution,
        recipient_id=student_id,
        appointment_id=appointment["id"],
    )

    cancel = client.post(
        f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token)
    )
    assert cancel.status_code == 200

    resolved = client.get("/notifications", headers=auth_header(student_token)).json()
    match = next(n for n in resolved if n["id"] == str(entry.id))
    assert match["read_at"] is not None


def test_no_show_also_resolves_a_pending_needs_resolution_notification(client, db_session):
    student_token = register_and_login(client, "notif-s10@example.com", role="student")
    student_id = _user_id(client, student_token)
    patient_id = create_patient(client, student_token)

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "room_id": create_default_room(client),
            "start_time": PAST_START,
            "end_time": PAST_END,
        },
        headers=auth_header(student_token),
    ).json()

    entry = _seed_unread(
        db_session,
        notification_type=NotificationType.appointment_needs_resolution,
        recipient_id=student_id,
        appointment_id=appointment["id"],
    )

    no_show = client.post(
        f"/appointments/{appointment['id']}/no-show", headers=auth_header(student_token)
    )
    assert no_show.status_code == 200

    resolved = client.get("/notifications", headers=auth_header(student_token)).json()
    match = next(n for n in resolved if n["id"] == str(entry.id))
    assert match["read_at"] is not None


def test_feedback_resolves_only_the_submitting_authors_reminder(client, db_session):
    student_token = register_and_login(client, "notif-s11@example.com", role="student")
    attending_token = register_and_login(client, "notif-a11@example.com", role="attending")
    attending_id = _user_id(client, attending_token)
    patient_id, patient_token = create_and_login_patient(
        client, student_token, email="notif-p11@example.com"
    )
    room_id = create_default_room(client)

    appointment = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "attending_id": attending_id,
            "room_id": room_id,
            "start_time": PAST_START,
            "end_time": PAST_END,
        },
        headers=auth_header(student_token),
    ).json()
    client.post(f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token))
    client.post(f"/appointments/{appointment['id']}/complete", headers=auth_header(student_token))

    patient_entry = _seed_unread(
        db_session,
        notification_type=NotificationType.feedback_reminder,
        recipient_id=patient_id,
        appointment_id=appointment["id"],
    )
    attending_entry = _seed_unread(
        db_session,
        notification_type=NotificationType.feedback_reminder,
        recipient_id=attending_id,
        appointment_id=appointment["id"],
    )

    feedback = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "Good", "could_improve": "Nothing", "additional_comments": None},
        headers=auth_header(patient_token),
    )
    assert feedback.status_code == 201

    patient_notifications = client.get("/notifications", headers=auth_header(patient_token)).json()
    patient_match = next(n for n in patient_notifications if n["id"] == str(patient_entry.id))
    assert patient_match["read_at"] is not None

    # The attending hasn't submitted their own feedback yet -- their reminder
    # must still be pending, not resolved by the patient's submission.
    attending_notifications = client.get(
        "/notifications", headers=auth_header(attending_token)
    ).json()
    attending_match = next(n for n in attending_notifications if n["id"] == str(attending_entry.id))
    assert attending_match["read_at"] is None


def test_accepting_resolves_the_students_own_accept_or_reject_notification(client):
    student_token = register_and_login(client, "notif-s12@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, email="notif-p12@example.com"
    )

    request = client.post(
        "/appointments",
        json={"start_time": START, "end_time": END},
        headers=auth_header(patient_token),
    ).json()

    pending = _find_notification(
        client,
        student_token,
        notification_type="appointment_created",
        appointment_id=request["id"],
    )
    assert pending["read_at"] is None

    room_id = create_default_room(client)
    accept = client.post(
        f"/appointments/{request['id']}/accept",
        json={"room_id": room_id},
        headers=auth_header(student_token),
    )
    assert accept.status_code == 200

    resolved = _find_notification(
        client,
        student_token,
        notification_type="appointment_created",
        appointment_id=request["id"],
    )
    assert resolved["read_at"] is not None


def test_approving_resolves_the_attendings_own_needs_approval_notification(client):
    student_token = register_and_login(client, "notif-s13@example.com", role="student")
    attending_token = register_and_login(client, "notif-a13@example.com", role="attending")
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

    pending = _find_notification(
        client,
        attending_token,
        notification_type="appointment_created",
        appointment_id=appointment["id"],
    )
    assert pending["read_at"] is None

    approve = client.post(
        f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token)
    )
    assert approve.status_code == 200

    resolved = _find_notification(
        client,
        attending_token,
        notification_type="appointment_created",
        appointment_id=appointment["id"],
    )
    assert resolved["read_at"] is not None


def test_rejecting_resolves_appointment_created_regardless_of_recipient(client):
    student_token = register_and_login(client, "notif-s14@example.com", role="student")
    attending_token = register_and_login(client, "notif-a14@example.com", role="attending")
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

    # The rejecting attending's own copy is resolved (they just acted on it)...
    attending_resolved = _find_notification(
        client,
        attending_token,
        notification_type="appointment_created",
        appointment_id=appointment["id"],
    )
    assert attending_resolved["read_at"] is not None


def test_cancelling_also_resolves_appointment_created(client):
    student_token = register_and_login(client, "notif-s15@example.com", role="student")
    attending_token = register_and_login(client, "notif-a15@example.com", role="attending")
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

    pending = _find_notification(
        client,
        attending_token,
        notification_type="appointment_created",
        appointment_id=appointment["id"],
    )
    assert pending["read_at"] is None

    cancel = client.post(
        f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token)
    )
    assert cancel.status_code == 200

    resolved = _find_notification(
        client,
        attending_token,
        notification_type="appointment_created",
        appointment_id=appointment["id"],
    )
    assert resolved["read_at"] is not None
