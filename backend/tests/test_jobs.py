from datetime import UTC, datetime, timedelta

from app.jobs.expiry import expire_stale_appointments
from app.jobs.reminders import send_appointment_reminders
from app.models.appointment import Appointment, AppointmentStatus
from tests.helpers import auth_header, create_patient, register_and_login


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _book(client, token, *, patient_id, attending_id=None, start_time, end_time):
    body = {"patient_id": patient_id, "start_time": start_time, "end_time": end_time}
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


def test_expire_triggers_waitlist_match(client, db_session):
    student_token = register_and_login(client, "job-s8@example.com", role="student")
    attending_token = register_and_login(client, "job-a8@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    other_student_token = register_and_login(client, "job-s8b@example.com", role="student")
    other_patient_id = create_patient(client, other_student_token)

    now = datetime.now(UTC)
    start = now - timedelta(hours=2)
    end = now - timedelta(hours=1)

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

    appointment = _book(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        start_time=_iso(start),
        end_time=_iso(end),
    ).json()
    assert appointment["status"] == "awaiting_confirmation"

    row = db_session.get(Appointment, appointment["id"])
    row.status = AppointmentStatus.proposed
    row.student_confirmed_at = None
    db_session.commit()

    assert expire_stale_appointments(db_session) == 1

    updated_entry = client.get(
        f"/waitlist/{waitlist_entry['id']}", headers=auth_header(other_student_token)
    ).json()
    assert updated_entry["status"] == "notified"


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
