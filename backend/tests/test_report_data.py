from datetime import UTC, datetime, timedelta

from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import User
from app.services.report_data import resource_utilization, time_impact
from tests.helpers import auth_header, create_patient, create_room, register_and_login


def _make_appointment(
    db_session,
    *,
    student_id,
    patient_id,
    attending_id=None,
    room_id=None,
    equipment_id=None,
    status,
    start_time,
    end_time,
):
    appointment = Appointment(
        student_id=student_id,
        patient_id=patient_id,
        attending_id=attending_id,
        room_id=room_id,
        equipment_id=equipment_id,
        start_time=start_time,
        end_time=end_time,
        status=status,
    )
    db_session.add(appointment)
    db_session.commit()
    return appointment


def test_resource_utilization_computes_hours_and_deviation(client, db_session):
    admin_token = register_and_login(client, "rd-admin1@example.com", role="admin")
    student_token = register_and_login(client, "rd-s1@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    room_a = create_room(client, admin_token, name="Room RD-A")
    create_room(client, admin_token, name="Room RD-B")

    now = datetime.now(UTC)
    start = now - timedelta(days=5)

    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        room_id=room_a,
        status=AppointmentStatus.completed,
        start_time=start,
        end_time=start + timedelta(hours=1),
    )
    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        room_id=room_a,
        status=AppointmentStatus.completed,
        start_time=start + timedelta(hours=2),
        end_time=start + timedelta(hours=3),
    )

    results = resource_utilization(db_session, start=now - timedelta(days=7), end=now)
    by_name = {r["resource_name"]: r for r in results if r["resource_type"] == "room"}

    assert by_name["Room RD-A"]["booked_hours"] == 2.0
    assert by_name["Room RD-A"]["appointment_count"] == 2
    assert by_name["Room RD-B"]["booked_hours"] == 0.0
    assert by_name["Room RD-B"]["appointment_count"] == 0
    assert by_name["Room RD-A"]["average_booked_hours_for_type"] == 1.0
    assert by_name["Room RD-A"]["deviation_from_average"] == 1.0
    assert by_name["Room RD-B"]["deviation_from_average"] == -1.0


def test_resource_utilization_excludes_non_utilized_status(client, db_session):
    admin_token = register_and_login(client, "rd-admin3@example.com", role="admin")
    student_token = register_and_login(client, "rd-s7@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token)
    room_id = create_room(client, admin_token, name="Room RD-C")

    now = datetime.now(UTC)
    start = now - timedelta(days=1)
    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        room_id=room_id,
        status=AppointmentStatus.proposed,
        start_time=start,
        end_time=start + timedelta(hours=1),
    )

    results = resource_utilization(db_session, start=now - timedelta(days=7), end=now)
    room_c = next(r for r in results if r["resource_name"] == "Room RD-C")
    assert room_c["booked_hours"] == 0.0
    assert room_c["appointment_count"] == 0


def test_time_impact_scoped_to_own_appointments(client, db_session):
    student_token = register_and_login(client, "rd-s2@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token, full_name="Impact Patient")

    other_student_token = register_and_login(client, "rd-s3@example.com", role="student")
    other_student_id = client.get("/users/me", headers=auth_header(other_student_token)).json()[
        "id"
    ]
    other_patient_id = create_patient(client, other_student_token, full_name="Other Patient")

    now = datetime.now(UTC)
    start = now - timedelta(days=2)

    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        status=AppointmentStatus.no_show,
        start_time=start,
        end_time=start + timedelta(minutes=30),
    )
    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        status=AppointmentStatus.cancelled,
        start_time=start + timedelta(hours=1),
        end_time=start + timedelta(hours=2),
    )
    _make_appointment(
        db_session,
        student_id=other_student_id,
        patient_id=other_patient_id,
        status=AppointmentStatus.cancelled,
        start_time=start,
        end_time=start + timedelta(hours=1),
    )

    student = db_session.get(User, student_id)
    results = time_impact(db_session, scope_user=student, start=now - timedelta(days=7), end=now)

    assert len(results) == 1
    assert results[0]["actor_type"] == "patient"
    assert results[0]["actor_id"] == patient_id
    assert results[0]["no_show_count"] == 1
    assert results[0]["cancelled_count"] == 1
    assert results[0]["minutes_lost"] == 90.0


def test_time_impact_includes_attending_actor_for_student_scope(client, db_session):
    student_token = register_and_login(client, "rd-s4@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token)
    attending_token = register_and_login(client, "rd-a1@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]

    now = datetime.now(UTC)
    start = now - timedelta(days=1)
    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        attending_id=attending_id,
        status=AppointmentStatus.cancelled,
        start_time=start,
        end_time=start + timedelta(hours=1),
    )

    student = db_session.get(User, student_id)
    results = time_impact(db_session, scope_user=student, start=now - timedelta(days=7), end=now)
    actor_types = {r["actor_type"] for r in results}
    assert actor_types == {"patient", "attending"}


def test_time_impact_includes_student_actor_for_attending_scope(client, db_session):
    student_token = register_and_login(client, "rd-s5@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token)
    attending_token = register_and_login(client, "rd-a2@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]

    now = datetime.now(UTC)
    start = now - timedelta(days=1)
    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        attending_id=attending_id,
        status=AppointmentStatus.no_show,
        start_time=start,
        end_time=start + timedelta(hours=1),
    )

    attending = db_session.get(User, attending_id)
    results = time_impact(db_session, scope_user=attending, start=now - timedelta(days=7), end=now)
    actor_types = {r["actor_type"] for r in results}
    assert actor_types == {"patient", "student"}


def test_time_impact_excludes_appointments_outside_window(client, db_session):
    student_token = register_and_login(client, "rd-s6@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token)

    now = datetime.now(UTC)
    old_start = now - timedelta(days=100)
    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        status=AppointmentStatus.cancelled,
        start_time=old_start,
        end_time=old_start + timedelta(hours=1),
    )

    student = db_session.get(User, student_id)
    results = time_impact(db_session, scope_user=student, start=now - timedelta(days=7), end=now)
    assert results == []


def test_resource_utilization_clips_boundary_spanning_appointment_to_overlap(client, db_session):
    admin_token = register_and_login(client, "rd-admin4@example.com", role="admin")
    student_token = register_and_login(client, "rd-s10@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    patient_id = create_patient(client, student_token)
    room_id = create_room(client, admin_token, name="Room RD-D")

    now = datetime.now(UTC)
    period_start = now - timedelta(days=7)
    # Starts 1 hour before the period and runs 1 hour into it -- only the
    # 1 hour that actually falls inside [period_start, now) should count,
    # and the appointment must not be excluded outright for starting
    # before the window.
    _make_appointment(
        db_session,
        student_id=student_id,
        patient_id=patient_id,
        room_id=room_id,
        status=AppointmentStatus.completed,
        start_time=period_start - timedelta(hours=1),
        end_time=period_start + timedelta(hours=1),
    )

    results = resource_utilization(db_session, start=period_start, end=now)
    room_d = next(r for r in results if r["resource_name"] == "Room RD-D")
    assert room_d["booked_hours"] == 1.0
    assert room_d["appointment_count"] == 1


def test_time_impact_returns_empty_for_non_student_non_attending_scope(client, db_session):
    admin_token = register_and_login(client, "rd-admin2@example.com", role="admin")
    admin_id = client.get("/users/me", headers=auth_header(admin_token)).json()["id"]
    admin = db_session.get(User, admin_id)

    now = datetime.now(UTC)
    results = time_impact(db_session, scope_user=admin, start=now - timedelta(days=7), end=now)
    assert results == []
