import threading
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import RoleEnum, User
from tests.conftest import engine
from tests.helpers import (
    auth_header,
    create_and_login_patient,
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
    conflicts = second.json()["conflicts"]
    assert [c["resource_type"] for c in conflicts] == ["student"]


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
    conflicts = second.json()["conflicts"]
    assert sorted(c["resource_type"] for c in conflicts) == ["patient", "student"]


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
    conflicts = second.json()["conflicts"]
    assert [c["resource_type"] for c in conflicts] == ["attending"]
    assert conflicts[0]["resource_id"] == attending_id


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
    conflicts = second.json()["conflicts"]
    assert [c["resource_type"] for c in conflicts] == ["room"]
    assert conflicts[0]["resource_id"] == room_id


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
    conflicts = second.json()["conflicts"]
    assert [c["resource_type"] for c in conflicts] == ["equipment"]
    assert conflicts[0]["resource_id"] == equipment_id


def test_multiple_simultaneous_conflicts_are_all_reported(client):
    student_a = register_and_login(client, "conf-s5c@example.com", role="student")
    student_b = register_and_login(client, "conf-s5d@example.com", role="student")
    attending_token = register_and_login(client, "conf-a5c@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    admin_token = register_and_login(client, "conf-admin5c@example.com", role="admin")
    room_id = create_room(client, admin_token, "Conflict Room Multi")
    patient_a = create_patient(client, student_a)
    patient_b = create_patient(client, student_b)

    first = _book(
        client, student_a, patient_id=patient_a, attending_id=attending_id, room_id=room_id
    )
    assert first.status_code == 201

    second = _book(
        client,
        student_b,
        patient_id=patient_b,
        attending_id=attending_id,
        room_id=room_id,
        start_time=OVERLAP_START,
        end_time=OVERLAP_END,
    )
    assert second.status_code == 409
    conflicts = second.json()["conflicts"]
    assert sorted(c["resource_type"] for c in conflicts) == ["attending", "room"]


def test_patient_never_learns_their_student_is_busy_with_someone_else(client):
    """A patient-originated request can conflict on "student" -- their
    treating student has some other overlapping appointment, possibly with
    a completely different patient. The patient must never see that: no
    "student" resource_type, no student id/name, nothing that lets them
    infer their student's other patients' schedules. It should present
    identically to a genuine self-conflict.
    """
    student_token = register_and_login(client, "conf-s7@example.com", role="student")
    other_patient = create_patient(client, student_token, full_name="Other Patient")
    _, requesting_patient_token = create_and_login_patient(
        client, student_token, "conf-p7@example.com", full_name="Requesting Patient"
    )

    # The student's own booking with a *different* patient occupies the
    # shared treating student at this time.
    occupied = _book(client, student_token, patient_id=other_patient)
    assert occupied.status_code == 201

    # The requesting patient's own overlapping request conflicts on
    # "student" underneath, but must be redacted before it leaves the API.
    response = client.post(
        "/appointments",
        json={"start_time": START, "end_time": END},
        headers=auth_header(requesting_patient_token),
    )
    assert response.status_code == 409
    conflicts = response.json()["conflicts"]

    assert [c["resource_type"] for c in conflicts] == ["patient"]
    requesting_patient_id = client.get(
        "/users/me", headers=auth_header(requesting_patient_token)
    ).json()["id"]
    assert conflicts[0]["resource_id"] == requesting_patient_id
    assert conflicts[0]["resource_name"] == "Requesting Patient"

    # Nothing about the student or the other patient leaks anywhere in the
    # response body.
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]
    body_text = response.text
    assert "Other Patient" not in body_text
    assert student_id not in body_text


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


def test_update_into_conflicting_room_rejected(client):
    occupier_token = register_and_login(client, "conf-s8-occ@example.com", role="student")
    admin_token = register_and_login(client, "conf-admin8@example.com", role="admin")
    room_id = create_room(client, admin_token, "Update Conflict Room")
    occupier_patient_id = create_patient(client, occupier_token)
    occupied = _book(client, occupier_token, patient_id=occupier_patient_id, room_id=room_id)
    assert occupied.status_code == 201

    student_token = register_and_login(client, "conf-s8@example.com", role="student")
    patient_id = create_patient(client, student_token)
    other_room_id = create_default_room(client)
    movable = _book(
        client,
        student_token,
        patient_id=patient_id,
        room_id=other_room_id,
        start_time=OVERLAP_START,
        end_time=OVERLAP_END,
    ).json()

    response = client.patch(
        f"/appointments/{movable['id']}",
        json={"room_id": room_id, "start_time": START, "end_time": END},
        headers=auth_header(student_token),
    )
    assert response.status_code == 409
    conflicts = response.json()["conflicts"]
    assert [c["resource_type"] for c in conflicts] == ["room"]

    # The appointment must be left untouched -- the conflict was checked
    # before any field was mutated.
    unchanged = client.get(
        f"/appointments/{movable['id']}", headers=auth_header(student_token)
    ).json()
    assert unchanged["room_id"] == other_room_id
    assert datetime.fromisoformat(unchanged["start_time"]) == datetime.fromisoformat(OVERLAP_START)


def test_accept_with_conflicting_room_rejected(client):
    occupier_token = register_and_login(client, "conf-s9-occ@example.com", role="student")
    admin_token = register_and_login(client, "conf-admin9@example.com", role="admin")
    room_id = create_room(client, admin_token, "Accept Conflict Room")
    occupier_patient_id = create_patient(client, occupier_token)
    occupied = _book(
        client,
        occupier_token,
        patient_id=occupier_patient_id,
        room_id=room_id,
        start_time=START,
        end_time=END,
    )
    assert occupied.status_code == 201

    student_token = register_and_login(client, "conf-s9@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "conf-p9@example.com")
    proposed = client.post(
        "/appointments",
        json={"start_time": START, "end_time": END},
        headers=auth_header(patient_token),
    ).json()
    assert proposed["status"] == "proposed"

    response = client.post(
        f"/appointments/{proposed['id']}/accept",
        json={"room_id": room_id},
        headers=auth_header(student_token),
    )
    assert response.status_code == 409
    conflicts = response.json()["conflicts"]
    assert [c["resource_type"] for c in conflicts] == ["room"]


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
