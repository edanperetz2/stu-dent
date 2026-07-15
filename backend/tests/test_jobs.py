from datetime import UTC, datetime, timedelta

from app.jobs.expiry import expire_stale_appointments
from app.jobs.feedback_reminders import notify_pending_feedback
from app.jobs.reminders import send_appointment_reminders
from app.jobs.unresolved_appointments import notify_unresolved_past_appointments
from app.models.appointment import Appointment, AppointmentStatus
from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_default_room,
    create_patient,
    register_and_login,
)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _book(client, token, *, patient_id, attending_id=None, room_id=None, start_time, end_time):
    if room_id is None:
        room_id = create_default_room(client)
    body = {
        "patient_id": patient_id,
        "room_id": room_id,
        "start_time": start_time,
        "end_time": end_time,
    }
    if attending_id is not None:
        body["attending_id"] = attending_id
    return client.post("/appointments", json=body, headers=auth_header(token))


def test_reminder_sent_for_confirmed_appointment_in_window(client, db_session):
    student_token = register_and_login(client, "job-s1@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=2)
    appointment = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()
    assert appointment["status"] == "confirmed"

    sent = send_appointment_reminders(db_session)
    assert sent == 1

    row = db_session.get(Appointment, appointment["id"])
    assert row.reminder_sent_at is not None

    notifications = client.get("/notifications", headers=auth_header(student_token)).json()
    assert any(n["notification_type"] == "appointment_reminder" for n in notifications)


def test_reminder_not_sent_twice(client, db_session):
    student_token = register_and_login(client, "job-s2@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=2)
    _book(client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end))

    assert send_appointment_reminders(db_session) == 1
    assert send_appointment_reminders(db_session) == 0


def test_reminder_skips_appointment_outside_window(client, db_session):
    student_token = register_and_login(client, "job-s3@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now + timedelta(hours=48)
    end = now + timedelta(hours=49)
    _book(client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end))

    assert send_appointment_reminders(db_session) == 0


def test_reminder_skips_non_confirmed_appointment(client, db_session):
    student_token = register_and_login(client, "job-s4@example.com", role="student")
    attending_token = register_and_login(client, "job-a4@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=2)
    appointment = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        start_time=_iso(start),
        end_time=_iso(end),
    ).json()
    assert appointment["status"] == "awaiting_confirmation"

    assert send_appointment_reminders(db_session) == 0


def test_reminder_includes_assigned_attending(client, db_session):
    student_token = register_and_login(client, "job-s5@example.com", role="student")
    attending_token = register_and_login(client, "job-a5@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now + timedelta(hours=1)
    end = now + timedelta(hours=2)
    appointment = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        start_time=_iso(start),
        end_time=_iso(end),
    ).json()
    client.post(f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token))

    assert send_appointment_reminders(db_session) == 1

    notifications = client.get("/notifications", headers=auth_header(attending_token)).json()
    assert any(n["notification_type"] == "appointment_reminder" for n in notifications)


def test_expire_cancels_past_due_unconfirmed_appointment(client, db_session):
    student_token = register_and_login(client, "job-s6@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = now - timedelta(hours=1)
    appointment = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()
    assert appointment["status"] == "confirmed"

    # Force it back to a pending state as if it had never been confirmed,
    # simulating a patient-initiated request that sat unactioned.
    row = db_session.get(Appointment, appointment["id"])
    row.status = AppointmentStatus.proposed
    row.student_confirmed_at = None
    db_session.commit()

    expired = expire_stale_appointments(db_session)
    assert expired == 1

    row = db_session.get(Appointment, appointment["id"])
    assert row.status == AppointmentStatus.cancelled

    notifications = client.get("/notifications", headers=auth_header(student_token)).json()
    assert any(n["notification_type"] == "appointment_expired" for n in notifications)


def test_expire_triggers_waitlist_promotion(client, db_session):
    student_token = register_and_login(client, "job-s8@example.com", role="student")
    attending_token = register_and_login(client, "job-a8@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    other_student_token = register_and_login(client, "job-s8b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = now - timedelta(hours=1)

    appointment = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        start_time=_iso(start),
        end_time=_iso(end),
    ).json()
    assert appointment["status"] == "awaiting_confirmation"

    # Only joinable once the attending is genuinely busy -- i.e. after the
    # conflicting appointment above already exists.
    waitlist_entry = client.post(
        "/waitlist",
        json={
            "patient_id": other_patient_id,
            "attending_id": attending_id,
            "start_time": _iso(start),
            "end_time": _iso(end),
        },
        headers=auth_header(other_student_token),
    ).json()
    assert waitlist_entry["status"] == "active"

    row = db_session.get(Appointment, appointment["id"])
    row.status = AppointmentStatus.proposed
    row.student_confirmed_at = None
    db_session.commit()

    assert expire_stale_appointments(db_session) == 1

    updated_entry = client.get(
        f"/waitlist/{waitlist_entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "booked"
    assert updated_entry["resulting_appointment_id"] is not None


def test_expire_does_not_touch_confirmed_or_terminal_appointments(client, db_session):
    student_token = register_and_login(client, "job-s7@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = now - timedelta(hours=1)
    confirmed = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()
    assert confirmed["status"] == "confirmed"

    assert expire_stale_appointments(db_session) == 0

    row = db_session.get(Appointment, confirmed["id"])
    assert row.status == AppointmentStatus.confirmed


def test_unresolved_notifies_confirmed_appointment_past_grace_period(client, db_session):
    student_token = register_and_login(client, "job-s9@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=30)
    end = now - timedelta(hours=29)
    appointment = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()
    assert appointment["status"] == "confirmed"

    notified = notify_unresolved_past_appointments(db_session)
    assert notified == 1

    notifications = client.get("/notifications", headers=auth_header(student_token)).json()
    assert any(n["notification_type"] == "appointment_needs_resolution" for n in notifications)


def test_unresolved_not_notified_again_within_grace_window(client, db_session):
    student_token = register_and_login(client, "job-s10@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=30)
    end = now - timedelta(hours=29)
    _book(client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end))

    assert notify_unresolved_past_appointments(db_session) == 1
    assert notify_unresolved_past_appointments(db_session) == 0


def test_unresolved_skips_appointment_still_within_grace_period(client, db_session):
    student_token = register_and_login(client, "job-s11@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = now - timedelta(hours=1)
    appointment = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()
    assert appointment["status"] == "confirmed"

    assert notify_unresolved_past_appointments(db_session) == 0


def test_unresolved_skips_terminal_appointments(client, db_session):
    student_token = register_and_login(client, "job-s12@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=30)
    end = now - timedelta(hours=29)
    appointment = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()

    client.post(f"/appointments/{appointment['id']}/cancel", headers=auth_header(student_token))

    assert notify_unresolved_past_appointments(db_session) == 0


def test_feedback_reminder_notifies_patient_and_attending_past_grace_period(client, db_session):
    student_token = register_and_login(client, "job-s13@example.com", role="student")
    attending_token = register_and_login(client, "job-a13@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "job-p13@example.com"
    )

    now = datetime.now(UTC)
    start = now - timedelta(hours=30)
    end = now - timedelta(hours=29)
    appointment = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        start_time=_iso(start),
        end_time=_iso(end),
    ).json()
    client.post(f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token))
    client.post(f"/appointments/{appointment['id']}/complete", headers=auth_header(student_token))

    notified = notify_pending_feedback(db_session)
    assert notified == 2

    patient_notifications = client.get("/notifications", headers=auth_header(patient_token)).json()
    assert any(n["notification_type"] == "feedback_reminder" for n in patient_notifications)
    attending_notifications = client.get(
        "/notifications", headers=auth_header(attending_token)
    ).json()
    assert any(n["notification_type"] == "feedback_reminder" for n in attending_notifications)


def test_feedback_reminder_not_notified_again_within_window(client, db_session):
    student_token = register_and_login(client, "job-s14@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=30)
    end = now - timedelta(hours=29)
    appointment = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()
    client.post(f"/appointments/{appointment['id']}/complete", headers=auth_header(student_token))

    assert notify_pending_feedback(db_session) == 1
    assert notify_pending_feedback(db_session) == 0


def test_feedback_reminder_skips_appointment_still_within_grace_period(client, db_session):
    student_token = register_and_login(client, "job-s15@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = now - timedelta(hours=1)
    appointment = _book(
        client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end)
    ).json()
    client.post(f"/appointments/{appointment['id']}/complete", headers=auth_header(student_token))

    assert notify_pending_feedback(db_session) == 0


def test_feedback_reminder_skips_non_completed_appointment(client, db_session):
    student_token = register_and_login(client, "job-s16@example.com", role="student")
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=30)
    end = now - timedelta(hours=29)
    _book(client, student_token, patient_id=patient_id, start_time=_iso(start), end_time=_iso(end))

    assert notify_pending_feedback(db_session) == 0


def test_feedback_reminder_stops_for_author_who_already_gave_feedback(client, db_session):
    student_token = register_and_login(client, "job-s17@example.com", role="student")
    attending_token = register_and_login(client, "job-a17@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "job-p17@example.com"
    )

    now = datetime.now(UTC)
    start = now - timedelta(hours=30)
    end = now - timedelta(hours=29)
    appointment = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        start_time=_iso(start),
        end_time=_iso(end),
    ).json()
    client.post(f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token))
    client.post(f"/appointments/{appointment['id']}/complete", headers=auth_header(student_token))

    client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x", "could_improve": "y"},
        headers=auth_header(patient_token),
    )

    # Patient already gave feedback -- only the attending is still pending.
    assert notify_pending_feedback(db_session) == 1
