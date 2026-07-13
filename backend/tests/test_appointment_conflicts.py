import threading
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import RoleEnum, User
from tests.conftest import engine
from tests.helpers import (
    auth_header,
    create_default_room,
    create_equipment,
    create_patient,
    create_room,
    register_and_login,
)

START = "2026-10-01T09:00:00+00:00"
END = "2026-10-01T10:00:00+00:00"
OVERLAP_START = "2026-10-01T09:30:00+00:00"
OVERLAP_END = "2026-10-01T10:30:00+00:00"


def _book(
    client,
    token,
    *,
    patient_id,
    attending_id=None,
    room_id=None,
    equipment_id=None,
    start_time=START,
    end_time=END,
):
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
    if equipment_id is not None:
        body["equipment_id"] = equipment_id
    return client.post("/appointments", json=body, headers=auth_header(token))


def test_overlapping_student_booking_conflicts(client):
    student_token = register_and_login(client, "conf-s1@example.com", role="student")
    patient_a = create_patient(client, student_token, full_name="Patient A")
    patient_b = create_patient(client, student_token, full_name="Patient B")

    first = _book(client, student_token, patient_id=patient_a)
    assert first.status_code == 201

    second = _book(
        client,
        student_token,
        patient_id=patient_b,
        start_time=OVERLAP_START,
        end_time=OVERLAP_END,
    )
    assert second.status_code == 409


def test_overlapping_patient_booking_conflicts(client):
    student_token = register_and_login(client, "conf-s2@example.com", role="student")
    patient_id = create_patient(client, student_token)

    first = _book(client, student_token, patient_id=patient_id)
    assert first.status_code == 201

    second = _book(
        client,
        student_token,
        patient_id=patient_id,
        start_time=OVERLAP_START,
        end_time=OVERLAP_END,
    )
    assert second.status_code == 409


def test_overlapping_attending_booking_conflicts(client):
    student_a = register_and_login(client, "conf-s3a@example.com", role="student")
    student_b = register_and_login(client, "conf-s3b@example.com", role="student")
    attending_token = register_and_login(client, "conf-a3@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_a = create_patient(client, student_a)
    patient_b = create_patient(client, student_b)

    first = _book(client, student_a, patient_id=patient_a, attending_id=attending_id)
    assert first.status_code == 201

    second = _book(
        client,
        student_b,
        patient_id=patient_b,
        attending_id=attending_id,
        start_time=OVERLAP_START,
        end_time=OVERLAP_END,
    )
    assert second.status_code == 409


def test_overlapping_room_booking_conflicts(client):
    student_a = register_and_login(client, "conf-s4a@example.com", role="student")
    student_b = register_and_login(client, "conf-s4b@example.com", role="student")
    admin_token = register_and_login(client, "conf-admin4@example.com", role="admin")
    room_id = create_room(client, admin_token, "Conflict Room")
    patient_a = create_patient(client, student_a)
    patient_b = create_patient(client, student_b)

    first = _book(client, student_a, patient_id=patient_a, room_id=room_id)
    assert first.status_code == 201

    second = _book(
        client,
        student_b,
        patient_id=patient_b,
        room_id=room_id,
        start_time=OVERLAP_START,
        end_time=OVERLAP_END,
    )
    assert second.status_code == 409


def test_overlapping_equipment_booking_conflicts(client):
    student_a = register_and_login(client, "conf-s5a@example.com", role="student")
    student_b = register_and_login(client, "conf-s5b@example.com", role="student")
    admin_token = register_and_login(client, "conf-admin5@example.com", role="admin")
    equipment_id = create_equipment(client, admin_token, "Conflict Equipment")
    patient_a = create_patient(client, student_a)
    patient_b = create_patient(client, student_b)

    first = _book(client, student_a, patient_id=patient_a, equipment_id=equipment_id)
    assert first.status_code == 201

    second = _book(
        client,
        student_b,
        patient_id=patient_b,
        equipment_id=equipment_id,
        start_time=OVERLAP_START,
        end_time=OVERLAP_END,
    )
    assert second.status_code == 409


def test_non_overlapping_bookings_do_not_conflict(client):
    student_token = register_and_login(client, "conf-s6@example.com", role="student")
    patient_id = create_patient(client, student_token)

    first = _book(client, student_token, patient_id=patient_id)
    assert first.status_code == 201

    second = _book(
        client,
        student_token,
        patient_id=patient_id,
        start_time=END,
        end_time="2026-10-01T11:00:00+00:00",
    )
    assert second.status_code == 201


def test_cancelled_appointment_frees_the_slot(client):
    student_token = register_and_login(client, "conf-s7@example.com", role="student")
    patient_a = create_patient(client, student_token, full_name="Patient A")
    patient_b = create_patient(client, student_token, full_name="Patient B")

    first = _book(client, student_token, patient_id=patient_a).json()
    client.post(f"/appointments/{first['id']}/cancel", headers=auth_header(student_token))

    second = _book(client, student_token, patient_id=patient_b)
    assert second.status_code == 201


def test_concurrent_overlapping_bookings_only_one_commits():
    """Real DB-level concurrency guarantee, bypassing the client/db_session fixture.

    That fixture wraps everything in one connection + SAVEPOINT rolled back at
    teardown, so a second thread's own connection would never see the first
    thread's row (MVCC visibility). This test uses the real `engine` and two
    independent `Session`s, with a `Barrier` so both threads race their
    `commit()` at the same time, to prove the exclusion constraint (not just
    the API's error-translation layer) actually serializes concurrent writers.
    """
    setup_session = Session(bind=engine)
    student_id = patient_a_id = patient_b_id = None
    try:
        student = User(
            email="concurrency-student@example.com",
            hashed_password="x",
            role=RoleEnum.student,
            full_name="Concurrency Student",
        )
        setup_session.add(student)
        setup_session.flush()
        patient_a = User(
            email="concurrency-patient-a@example.com",
            hashed_password="x",
            role=RoleEnum.patient,
            full_name="Concurrency Patient A",
            owner_student_id=student.id,
            owner_confirmed_at=datetime.now(UTC),
        )
        patient_b = User(
            email="concurrency-patient-b@example.com",
            hashed_password="x",
            role=RoleEnum.patient,
            full_name="Concurrency Patient B",
            owner_student_id=student.id,
            owner_confirmed_at=datetime.now(UTC),
        )
        setup_session.add_all([patient_a, patient_b])
        setup_session.commit()
        student_id, patient_a_id, patient_b_id = student.id, patient_a.id, patient_b.id
    finally:
        setup_session.close()

    start = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    end = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)

    barrier = threading.Barrier(2)
    results: dict[str, str] = {}

    def _attempt(key: str, patient_id) -> None:
        session = Session(bind=engine)
        try:
            appointment = Appointment(
                student_id=student_id,
                patient_id=patient_id,
                start_time=start,
                end_time=end,
                status=AppointmentStatus.confirmed,
                student_confirmed_at=start,
            )
            session.add(appointment)
            barrier.wait()
            session.commit()
            results[key] = "success"
        except IntegrityError:
            session.rollback()
            results[key] = "conflict"
        finally:
            session.close()

    thread_a = threading.Thread(target=_attempt, args=("a", patient_a_id))
    thread_b = threading.Thread(target=_attempt, args=("b", patient_b_id))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    try:
        assert sorted(results.values()) == ["conflict", "success"]
    finally:
        cleanup_session = Session(bind=engine)
        try:
            cleanup_session.query(Appointment).filter(Appointment.student_id == student_id).delete()
            cleanup_session.query(User).filter(User.owner_student_id == student_id).delete()
            cleanup_session.query(User).filter(User.id == student_id).delete()
            cleanup_session.commit()
        finally:
            cleanup_session.close()
