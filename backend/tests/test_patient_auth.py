from tests.helpers import (
    auth_header,
    confirm_patient,
    create_patient,
    login,
    register,
    register_and_login,
    register_patient,
)


def test_student_can_create_and_list_own_patients(client):
    token = register_and_login(client, "patauth-stud1@example.com", role="student")
    patient_id = create_patient(client, token, email="patauth-p1@example.com")

    list_response = client.get("/patients", headers=auth_header(token))
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == patient_id
    assert list_response.json()[0]["owner_confirmed_at"] is not None


def test_other_student_cannot_access_patient(client):
    token1 = register_and_login(client, "patauth-stud2@example.com", role="student")
    token2 = register_and_login(client, "patauth-stud3@example.com", role="student")
    patient_id = create_patient(client, token1, email="patauth-p2@example.com")

    response = client.get(f"/patients/{patient_id}", headers=auth_header(token2))
    assert response.status_code == 404


def test_student_provisioned_patient_can_log_in(client):
    token = register_and_login(
        client, "patauth-stud4@example.com", role="student", full_name="Dr. Mentor"
    )
    patient_id = create_patient(
        client, token, email="patauth-patient1@example.com", password="patientpass123"
    )

    login_response = login(client, "patauth-patient1@example.com", password="patientpass123")
    assert login_response.status_code == 200
    patient_token = login_response.json()["access_token"]

    me_response = client.get("/users/me", headers=auth_header(patient_token))
    assert me_response.status_code == 200
    assert me_response.json()["id"] == patient_id
    assert me_response.json()["role"] == "patient"
    assert me_response.json()["owner_student_name"] == "Dr. Mentor"


def test_patient_token_cannot_access_student_endpoints(client):
    token = register_and_login(client, "patauth-stud5@example.com", role="student")
    create_patient(client, token, email="patauth-patient2@example.com", password="patientpass123")
    patient_token = login(client, "patauth-patient2@example.com", password="patientpass123").json()[
        "access_token"
    ]

    response = client.get("/patients", headers=auth_header(patient_token))
    assert response.status_code == 403


def test_soft_deleted_patient_not_accessible(client):
    token = register_and_login(client, "patauth-stud7@example.com", role="student")
    patient_id = create_patient(client, token, email="patauth-p7@example.com")

    delete_response = client.delete(f"/patients/{patient_id}", headers=auth_header(token))
    assert delete_response.status_code == 204

    get_response = client.get(f"/patients/{patient_id}", headers=auth_header(token))
    assert get_response.status_code == 404

    list_response = client.get("/patients", headers=auth_header(token))
    assert list_response.json() == []


def test_patient_email_must_be_unique(client):
    token = register_and_login(client, "patauth-stud8@example.com", role="student")
    create_patient(client, token, full_name="Patient One", email="patauth-shared@example.com")
    response = client.post(
        "/patients",
        json={
            "full_name": "Patient Two",
            "email": "patauth-shared@example.com",
            "password": "password123",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 409


def test_patient_self_registration_is_pending_until_student_confirms(client):
    student_token = register_and_login(client, "patauth-stud9@example.com", role="student")
    student_id = client.get("/users/me", headers=auth_header(student_token)).json()["id"]

    patient_token = register_patient(client, student_id, "patauth-selfreg1@example.com")

    me = client.get("/users/me", headers=auth_header(patient_token)).json()
    assert me["owner_confirmed_at"] is None
    assert me["owner_student_id"] == student_id
    assert me["owner_student_name"] == "Test User"

    blocked_response = client.post(
        "/appointments",
        json={"start_time": "2030-01-01T10:00:00Z", "end_time": "2030-01-01T11:00:00Z"},
        headers=auth_header(patient_token),
    )
    assert blocked_response.status_code == 403

    patients = client.get("/patients", headers=auth_header(student_token)).json()
    pending = next(p for p in patients if p["email"] == "patauth-selfreg1@example.com")
    assert pending["owner_confirmed_at"] is None

    confirm_response = confirm_patient(client, student_token, pending["id"])
    assert confirm_response.status_code == 200
    assert confirm_response.json()["owner_confirmed_at"] is not None

    allowed_response = client.post(
        "/appointments",
        json={"start_time": "2030-01-01T10:00:00Z", "end_time": "2030-01-01T11:00:00Z"},
        headers=auth_header(patient_token),
    )
    assert allowed_response.status_code == 201


def test_patient_registration_requires_valid_owner_student_id(client):
    response = register(
        client,
        "patauth-selfreg2@example.com",
        role="patient",
        owner_student_id="00000000-0000-0000-0000-000000000000",
    )
    assert response.status_code == 422


def test_login_role_mismatch_rejected(client):
    register_and_login(client, "patauth-stud10@example.com", role="student")
    response = login(client, "patauth-stud10@example.com", role="attending")
    assert response.status_code == 401
