from tests.helpers import auth_header, create_and_login_patient, create_patient, register_and_login


def test_student_sends_message(client):
    student_token = register_and_login(client, "dm-s1@example.com", role="student")
    patient_id = create_patient(client, student_token)

    response = client.post(
        f"/patients/{patient_id}/messages",
        json={"body": "Hello patient"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["body"] == "Hello patient"
    assert body["sender_user_id"] is not None
    assert body["sender_patient_id"] is None
    assert body["read_at"] is None


def test_patient_sends_message(client):
    student_token = register_and_login(client, "dm-s2@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "dm-p2@example.com")

    response = client.post(
        f"/patients/{patient_id}/messages",
        json={"body": "Hello student"},
        headers=auth_header(patient_token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["sender_patient_id"] is not None
    assert body["sender_user_id"] is None


def test_thread_ordering_oldest_first(client):
    student_token = register_and_login(client, "dm-s3@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "dm-p3@example.com")

    client.post(
        f"/patients/{patient_id}/messages",
        json={"body": "first"},
        headers=auth_header(student_token),
    )
    client.post(
        f"/patients/{patient_id}/messages",
        json={"body": "second"},
        headers=auth_header(patient_token),
    )

    response = client.get(f"/patients/{patient_id}/messages", headers=auth_header(student_token))
    body = response.json()
    assert len(body) == 2
    assert body[0]["body"] == "first"
    assert body[1]["body"] == "second"


def test_patient_marks_student_sent_message_read(client):
    student_token = register_and_login(client, "dm-s4@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "dm-p4@example.com")

    message = client.post(
        f"/patients/{patient_id}/messages",
        json={"body": "from student"},
        headers=auth_header(student_token),
    ).json()

    response = client.post(
        f"/patients/{patient_id}/messages/{message['id']}/read",
        headers=auth_header(patient_token),
    )
    assert response.status_code == 200
    assert response.json()["read_at"] is not None


def test_student_marks_patient_sent_message_read(client):
    student_token = register_and_login(client, "dm-s5@example.com", role="student")
    patient_id, patient_token = create_and_login_patient(client, student_token, "dm-p5@example.com")

    message = client.post(
        f"/patients/{patient_id}/messages",
        json={"body": "from patient"},
        headers=auth_header(patient_token),
    ).json()

    response = client.post(
        f"/patients/{patient_id}/messages/{message['id']}/read",
        headers=auth_header(student_token),
    )
    assert response.status_code == 200
    assert response.json()["read_at"] is not None


def test_sender_cannot_mark_own_message_read(client):
    student_token = register_and_login(client, "dm-s6@example.com", role="student")
    patient_id = create_patient(client, student_token)

    message = client.post(
        f"/patients/{patient_id}/messages",
        json={"body": "from student"},
        headers=auth_header(student_token),
    ).json()

    response = client.post(
        f"/patients/{patient_id}/messages/{message['id']}/read",
        headers=auth_header(student_token),
    )
    assert response.status_code == 403


def test_third_party_gets_404_not_403(client):
    student_token = register_and_login(client, "dm-s7@example.com", role="student")
    other_student_token = register_and_login(client, "dm-s7b@example.com", role="student")
    attending_token = register_and_login(client, "dm-a7@example.com", role="attending")
    patient_id, _ = create_and_login_patient(client, student_token, "dm-p7@example.com")
    _, other_patient_token = create_and_login_patient(
        client, other_student_token, "dm-p7b@example.com"
    )

    assert (
        client.get(
            f"/patients/{patient_id}/messages", headers=auth_header(other_student_token)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/patients/{patient_id}/messages", headers=auth_header(attending_token)
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/patients/{patient_id}/messages", headers=auth_header(other_patient_token)
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/patients/{patient_id}/messages",
            json={"body": "intrusion"},
            headers=auth_header(other_student_token),
        ).status_code
        == 404
    )


def test_message_on_nonexistent_patient_404(client):
    student_token = register_and_login(client, "dm-s8@example.com", role="student")
    response = client.post(
        "/patients/00000000-0000-0000-0000-000000000000/messages",
        json={"body": "hi"},
        headers=auth_header(student_token),
    )
    assert response.status_code == 404


def test_messages_require_authentication(client):
    patient_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/patients/{patient_id}/messages").status_code == 401
    assert client.post(f"/patients/{patient_id}/messages", json={"body": "hi"}).status_code == 401
