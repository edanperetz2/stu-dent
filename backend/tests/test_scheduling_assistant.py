from datetime import datetime, timedelta

from app.services import ollama_client
from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_equipment,
    create_patient,
    create_room,
    register_and_login,
)


def _mock_ollama(monkeypatch, response: dict | None):
    monkeypatch.setattr(ollama_client, "generate_json", lambda prompt: response)


def test_interpret_requires_student_or_patient_role(client, monkeypatch):
    _mock_ollama(monkeypatch, {})
    attending_token = register_and_login(client, "sched-att1@example.com", role="attending")
    response = client.post(
        "/scheduling/interpret",
        json={"text": "book something"},
        headers=auth_header(attending_token),
    )
    assert response.status_code == 403


def test_interpret_resolves_names_and_date(client, monkeypatch):
    student_token = register_and_login(client, "sched-s1@example.com", role="student")
    admin_token = register_and_login(client, "sched-admin1@example.com", role="admin")
    attending_token = register_and_login(client, "sched-att2@example.com", role="attending")

    patient_id = create_patient(client, student_token, full_name="Jane Doe")
    room_id = create_room(client, admin_token, name="Room X-Ray")
    equipment_id = create_equipment(client, admin_token, name="Panoramic Scanner")
    attending_full_name = client.get("/users/me", headers=auth_header(attending_token)).json()[
        "full_name"
    ]

    _mock_ollama(
        monkeypatch,
        {
            "patient_name": "Jane",
            "attending_name": attending_full_name,
            "room_name": "X-Ray",
            "equipment_name": "Panoramic",
            "date_phrase": "friday",
            "time_of_day": "afternoon",
            "notes": "routine cleaning",
        },
    )

    response = client.post(
        "/scheduling/interpret",
        json={"text": "book Jane with Dr. Attending in the X-Ray room, scanner, friday afternoon"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] == patient_id
    assert body["room_id"] == room_id
    assert body["equipment_id"] == equipment_id
    assert body["start_time"] is not None
    assert body["end_time"] is not None
    assert body["warnings"] == []
    assert body["notes"] == "routine cleaning"

    start = datetime.fromisoformat(body["start_time"])
    end = datetime.fromisoformat(body["end_time"])
    assert start.hour == 13
    assert end - start == timedelta(minutes=30)


def test_interpret_unmatched_name_warns(client, monkeypatch):
    student_token = register_and_login(client, "sched-s2@example.com", role="student")
    create_patient(client, student_token, full_name="Jane Doe")

    _mock_ollama(
        monkeypatch,
        {
            "patient_name": "Nonexistent Person",
            "attending_name": None,
            "room_name": None,
            "equipment_name": None,
            "date_phrase": None,
            "time_of_day": None,
            "notes": None,
        },
    )

    response = client.post(
        "/scheduling/interpret",
        json={"text": "book Nonexistent Person"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] is None
    assert any("Nonexistent Person" in w for w in body["warnings"])


def test_interpret_ambiguous_name_warns(client, monkeypatch):
    student_token = register_and_login(client, "sched-s3@example.com", role="student")
    create_patient(client, student_token, full_name="Jane Doe", email="jane-doe@example.com")
    create_patient(client, student_token, full_name="Jane Smith", email="jane-smith@example.com")

    _mock_ollama(
        monkeypatch,
        {
            "patient_name": "Jane",
            "attending_name": None,
            "room_name": None,
            "equipment_name": None,
            "date_phrase": None,
            "time_of_day": None,
            "notes": None,
        },
    )

    response = client.post(
        "/scheduling/interpret",
        json={"text": "book Jane"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] is None
    assert any("Multiple" in w for w in body["warnings"])


def test_interpret_ollama_unavailable_returns_warning_no_500(client, monkeypatch):
    student_token = register_and_login(client, "sched-s4@example.com", role="student")
    _mock_ollama(monkeypatch, None)

    response = client.post(
        "/scheduling/interpret",
        json={"text": "book something"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] is None
    assert body["start_time"] is None
    assert len(body["warnings"]) == 1


def test_interpret_patient_role_does_not_resolve_attending_room_equipment(client, monkeypatch):
    student_token = register_and_login(client, "sched-s5@example.com", role="student")
    admin_token = register_and_login(client, "sched-admin2@example.com", role="admin")
    create_room(client, admin_token, name="Room Y")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, email="sched-patient1@example.com"
    )

    _mock_ollama(
        monkeypatch,
        {
            "patient_name": "irrelevant",
            "attending_name": "Nobody",
            "room_name": "Room Y",
            "equipment_name": "Nothing",
            "date_phrase": "tomorrow",
            "time_of_day": "morning",
            "notes": None,
        },
    )

    response = client.post(
        "/scheduling/interpret",
        json={"text": "book me in Room Y tomorrow morning"},
        headers=auth_header(patient_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] is None
    assert body["attending_id"] is None
    assert body["room_id"] is None
    assert body["equipment_id"] is None
    assert body["start_time"] is not None
    assert body["warnings"] == []


def test_interpret_non_string_fields_do_not_crash(client, monkeypatch):
    # Regression test: nothing enforces the model actually returns strings
    # for the fields the prompt asks for -- a non-string value used to
    # crash (AttributeError on `.strip()`, or TypeError on an unhashable
    # dict `.get()` key) instead of degrading to "couldn't resolve this
    # field" like a real string that just doesn't match anything.
    student_token = register_and_login(client, "sched-s7@example.com", role="student")
    _mock_ollama(
        monkeypatch,
        {
            "patient_name": ["not", "a", "string"],
            "attending_name": 42,
            "room_name": True,
            "equipment_name": {"nested": "object"},
            "date_phrase": ["also", "not", "a", "string"],
            "time_of_day": ["morning"],
            "notes": 123,
        },
    )

    response = client.post(
        "/scheduling/interpret",
        json={"text": "book something weird"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["patient_id"] is None
    assert body["attending_id"] is None
    assert body["room_id"] is None
    assert body["equipment_id"] is None
    assert body["start_time"] is None
    assert body["notes"] is None


def test_interpret_unresolvable_date_phrase_warns(client, monkeypatch):
    student_token = register_and_login(client, "sched-s6@example.com", role="student")
    _mock_ollama(
        monkeypatch,
        {
            "patient_name": None,
            "attending_name": None,
            "room_name": None,
            "equipment_name": None,
            "date_phrase": "someday eventually",
            "time_of_day": None,
            "notes": None,
        },
    )

    response = client.post(
        "/scheduling/interpret",
        json={"text": "book it someday eventually"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["start_time"] is None
    assert any("someday eventually" in w for w in body["warnings"])
