from tests.helpers import auth_header, register_and_login


def _create_patient(client, student_token, full_name="Pat Ient"):
    return client.post(
        "/patients",
        json={"full_name": full_name, "contact_phone": None},
        headers=auth_header(student_token),
    )


def test_student_can_create_and_list_own_patients(client):
    token = register_and_login(client, "patauth-stud1@example.com", role="student")
    response = _create_patient(client, token)
    assert response.status_code == 201

    list_response = client.get("/patients", headers=auth_header(token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_other_student_cannot_access_patient(client):
    token1 = register_and_login(client, "patauth-stud2@example.com", role="student")
    token2 = register_and_login(client, "patauth-stud3@example.com", role="student")
    patient_id = _create_patient(client, token1).json()["id"]

    response = client.get(f"/patients/{patient_id}", headers=auth_header(token2))
    assert response.status_code == 404


def test_student_provisions_patient_login_and_patient_can_log_in(client):
    token = register_and_login(client, "patauth-stud4@example.com", role="student")
    patient_id = _create_patient(client, token).json()["id"]

    cred_response = client.post(
        f"/patients/{patient_id}/credentials",
        json={"email": "patauth-patient1@example.com", "password": "patientpass123"},
        headers=auth_header(token),
    )
    assert cred_response.status_code == 200

    login_response = client.post(
        "/patients/login",
        json={"email": "patauth-patient1@example.com", "password": "patientpass123"},
    )
    assert login_response.status_code == 200
    patient_token = login_response.json()["access_token"]

    me_response = client.get("/patients/me", headers=auth_header(patient_token))
    assert me_response.status_code == 200
    assert me_response.json()["id"] == patient_id


def test_patient_token_cannot_access_student_endpoints(client):
    token = register_and_login(client, "patauth-stud5@example.com", role="student")
    patient_id = _create_patient(client, token).json()["id"]
    client.post(
        f"/patients/{patient_id}/credentials",
        json={"email": "patauth-patient2@example.com", "password": "patientpass123"},
        headers=auth_header(token),
    )
    patient_token = client.post(
        "/patients/login",
        json={"email": "patauth-patient2@example.com", "password": "patientpass123"},
    ).json()["access_token"]

    response = client.get("/patients", headers=auth_header(patient_token))
    assert response.status_code == 401


def test_user_token_cannot_access_patient_me(client):
    token = register_and_login(client, "patauth-stud6@example.com", role="student")
    response = client.get("/patients/me", headers=auth_header(token))
    assert response.status_code == 401


def test_soft_deleted_patient_not_accessible(client):
    token = register_and_login(client, "patauth-stud7@example.com", role="student")
    patient_id = _create_patient(client, token).json()["id"]

    delete_response = client.delete(f"/patients/{patient_id}", headers=auth_header(token))
    assert delete_response.status_code == 204

    get_response = client.get(f"/patients/{patient_id}", headers=auth_header(token))
    assert get_response.status_code == 404

    list_response = client.get("/patients", headers=auth_header(token))
    assert list_response.json() == []


def test_patient_credentials_email_must_be_unique(client):
    token = register_and_login(client, "patauth-stud8@example.com", role="student")
    patient1_id = _create_patient(client, token, full_name="Patient One").json()["id"]
    patient2_id = _create_patient(client, token, full_name="Patient Two").json()["id"]

    client.post(
        f"/patients/{patient1_id}/credentials",
        json={"email": "patauth-shared@example.com", "password": "patientpass123"},
        headers=auth_header(token),
    )
    conflict_response = client.post(
        f"/patients/{patient2_id}/credentials",
        json={"email": "patauth-shared@example.com", "password": "patientpass123"},
        headers=auth_header(token),
    )
    assert conflict_response.status_code == 409
