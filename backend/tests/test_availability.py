from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_patient,
    register_and_login,
)


def test_student_availability_starts_empty(client):
    student_token = register_and_login(client, "avail-s1@example.com", role="student")
    response = client.get("/students/me/availability", headers=auth_header(student_token))
    assert response.status_code == 200
    assert response.json() == []


def test_student_can_replace_availability(client):
    student_token = register_and_login(client, "avail-s2@example.com", role="student")
    windows = [
        {"day_of_week": 0, "start_time": "09:00:00", "end_time": "12:00:00"},
        {"day_of_week": 2, "start_time": "13:00:00", "end_time": "17:00:00"},
    ]
    response = client.put(
        "/students/me/availability", json=windows, headers=auth_header(student_token)
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {w["day_of_week"] for w in body} == {0, 2}

    get_response = client.get("/students/me/availability", headers=auth_header(student_token))
    assert len(get_response.json()) == 2


def test_replacing_availability_drops_previous_windows(client):
    student_token = register_and_login(client, "avail-s3@example.com", role="student")
    client.put(
        "/students/me/availability",
        json=[{"day_of_week": 1, "start_time": "09:00:00", "end_time": "10:00:00"}],
        headers=auth_header(student_token),
    )

    response = client.put(
        "/students/me/availability",
        json=[{"day_of_week": 3, "start_time": "14:00:00", "end_time": "15:00:00"}],
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["day_of_week"] == 3


def test_availability_rejects_invalid_time_range(client):
    student_token = register_and_login(client, "avail-s4@example.com", role="student")
    response = client.put(
        "/students/me/availability",
        json=[{"day_of_week": 0, "start_time": "12:00:00", "end_time": "09:00:00"}],
        headers=auth_header(student_token),
    )
    assert response.status_code == 422


def test_non_student_cannot_access_availability(client):
    attending_token = register_and_login(client, "avail-a1@example.com", role="attending")
    assert (
        client.get("/students/me/availability", headers=auth_header(attending_token)).status_code
        == 403
    )
    assert (
        client.put(
            "/students/me/availability", json=[], headers=auth_header(attending_token)
        ).status_code
        == 403
    )


def test_availability_requires_authentication(client):
    assert client.get("/students/me/availability").status_code == 401
    assert client.put("/students/me/availability", json=[]).status_code == 401


def test_student_sets_patient_preferred_time_of_day(client):
    student_token = register_and_login(client, "avail-s5@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = client.patch(
        f"/patients/{patient_id}",
        json={"preferred_time_of_day": "evening"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["preferred_time_of_day"] == "evening"


def test_patient_sees_own_preferred_time_of_day(client):
    student_token = register_and_login(client, "avail-s6@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(
        client, student_token, "avail-p6@example.com"
    )

    client.patch(
        f"/patients/{patient_id}",
        json={"preferred_time_of_day": "morning"},
        headers=auth_header(student_token),
    )

    response = client.get("/patients/me", headers=auth_header(patient_token))
    assert response.status_code == 200
    assert response.json()["preferred_time_of_day"] == "morning"


def test_invalid_preferred_time_of_day_rejected(client):
    student_token = register_and_login(client, "avail-s7@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = client.patch(
        f"/patients/{patient_id}",
        json={"preferred_time_of_day": "midnight"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 422
