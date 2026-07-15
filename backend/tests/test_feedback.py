from tests.helpers import (
    auth_header,
    create_and_login_patient,
    create_default_room,
    register_and_login,
)

START = "2020-08-01T09:00:00+00:00"
END = "2020-08-01T10:00:00+00:00"


def _book(client, token, *, patient_id=None, attending_id=None, room_id=None):
    body = {"start_time": START, "end_time": END}
    if patient_id is not None:
        body["patient_id"] = patient_id
        if room_id is None:
            room_id = create_default_room(client)
    if attending_id is not None:
        body["attending_id"] = attending_id
    if room_id is not None:
        body["room_id"] = room_id
    return client.post("/appointments", json=body, headers=auth_header(token))


def _book_and_complete(
    client, student_token, *, patient_id, attending_id=None, attending_token=None
):
    appointment = _book(
        client, student_token, patient_id=patient_id, attending_id=attending_id
    ).json()
    if attending_id is not None:
        client.post(
            f"/appointments/{appointment['id']}/approve", headers=auth_header(attending_token)
        )
    response = client.post(
        f"/appointments/{appointment['id']}/complete", headers=auth_header(student_token)
    )
    assert response.json()["status"] == "completed"
    return response.json()


def test_patient_and_attending_give_feedback_after_completion(client):
    student_token = register_and_login(client, "fb-s1@example.com", role="student")
    attending_token = register_and_login(client, "fb-a1@example.com", role="attending")
    attending_id = client.get("/users/me", headers=auth_header(attending_token)).json()["id"]
    patient_id, patient_token = create_and_login_patient(client, student_token, "fb-p1@example.com")

    appointment = _book_and_complete(
        client,
        student_token,
        patient_id=patient_id,
        attending_id=attending_id,
        attending_token=attending_token,
    )

    patient_response = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={
            "went_well": "Very gentle",
            "could_improve": "Nothing much",
            "additional_comments": None,
        },
        headers=auth_header(patient_token),
    )
    assert patient_response.status_code == 201
    body = patient_response.json()
    assert body["author_role"] == "patient"
    assert body["went_well"] == "Very gentle"
    assert body["additional_comments"] is None
    assert body["student_id"] == appointment["student_id"]

    attending_response = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={
            "went_well": "Good technique",
            "could_improve": "Faster next time",
            "additional_comments": "Keep it up",
        },
        headers=auth_header(attending_token),
    )
    assert attending_response.status_code == 201
    assert attending_response.json()["author_role"] == "attending"


def test_feedback_requires_completed_status(client):
    student_token = register_and_login(client, "fb-s2@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "fb-p2@example.com")

    appointment = _book(client, student_token, patient_id=patient_id).json()
    assert appointment["status"] == "confirmed"

    response = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x", "could_improve": "y"},
        headers=auth_header(patient_token),
    )
    assert response.status_code == 409


def test_feedback_requires_participant(client):
    student_token = register_and_login(client, "fb-s3@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "fb-p3@example.com")
    _, other_patient_token = create_and_login_patient(client, student_token, "fb-p3b@example.com")

    appointment = _book_and_complete(client, student_token, patient_id=patient_id)

    # A patient with no relation to this appointment can't even see it --
    # same 404-hides-existence convention as appointment visibility scoping.
    unrelated_response = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x", "could_improve": "y"},
        headers=auth_header(other_patient_token),
    )
    assert unrelated_response.status_code == 404

    # The owning student *can* see their own appointment but isn't a valid
    # feedback author on it (only the patient/attending are).
    student_response = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x", "could_improve": "y"},
        headers=auth_header(student_token),
    )
    assert student_response.status_code == 403


def test_feedback_duplicate_rejected(client):
    student_token = register_and_login(client, "fb-s4@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "fb-p4@example.com")

    appointment = _book_and_complete(client, student_token, patient_id=patient_id)

    first = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x", "could_improve": "y"},
        headers=auth_header(patient_token),
    )
    assert first.status_code == 201

    second = client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x2", "could_improve": "y2"},
        headers=auth_header(patient_token),
    )
    assert second.status_code == 409


def test_pending_feedback_excludes_already_given(client):
    student_token = register_and_login(client, "fb-s5@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "fb-p5@example.com")

    appointment = _book_and_complete(client, student_token, patient_id=patient_id)

    pending_before = client.get("/feedback/pending", headers=auth_header(patient_token)).json()
    assert any(p["appointment_id"] == appointment["id"] for p in pending_before)

    client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x", "could_improve": "y"},
        headers=auth_header(patient_token),
    )

    pending_after = client.get("/feedback/pending", headers=auth_header(patient_token)).json()
    assert not any(p["appointment_id"] == appointment["id"] for p in pending_after)


def test_feedback_given_and_received_role_gating(client):
    student_token = register_and_login(client, "fb-s6@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "fb-p6@example.com")

    appointment = _book_and_complete(client, student_token, patient_id=patient_id)
    client.post(
        f"/appointments/{appointment['id']}/feedback",
        json={"went_well": "x", "could_improve": "y"},
        headers=auth_header(patient_token),
    )

    given = client.get("/feedback/given", headers=auth_header(patient_token))
    assert given.status_code == 200
    assert len(given.json()) == 1
    assert given.json()[0]["went_well"] == "x"

    received = client.get("/feedback/received", headers=auth_header(student_token))
    assert received.status_code == 200
    assert len(received.json()) == 1
    assert received.json()[0]["author_role"] == "patient"

    assert client.get("/feedback/given", headers=auth_header(student_token)).status_code == 403
    assert client.get("/feedback/received", headers=auth_header(patient_token)).status_code == 403
