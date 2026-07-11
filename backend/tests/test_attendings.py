from tests.helpers import auth_header, create_and_login_patient, register_and_login


def test_student_can_list_active_attendings(client):
    student_token = register_and_login(client, "att-s1@example.com", role="student")
    register_and_login(client, "att-a1@example.com", role="attending", full_name="Dr. One")

    response = client.get("/attendings", headers=auth_header(student_token))
    assert response.status_code == 200
    names = [a["full_name"] for a in response.json()]
    assert "Dr. One" in names


def test_attendings_list_excludes_non_attendings(client):
    student_token = register_and_login(client, "att-s2@example.com", role="student")
    register_and_login(client, "att-s2b@example.com", role="student", full_name="Other Student")
    register_and_login(client, "att-admin2@example.com", role="admin", full_name="Some Admin")

    response = client.get("/attendings", headers=auth_header(student_token))
    names = [a["full_name"] for a in response.json()]
    assert "Other Student" not in names
    assert "Some Admin" not in names


def test_attendings_list_excludes_inactive(client):
    student_token = register_and_login(client, "att-s3@example.com", role="student")
    admin_token = register_and_login(client, "att-admin3@example.com", role="admin")
    register_and_login(client, "att-a3@example.com", role="attending", full_name="Dr. Inactive")

    users = client.get("/admin/users", headers=auth_header(admin_token)).json()
    target = next(u for u in users if u["full_name"] == "Dr. Inactive")
    client.patch(
        f"/admin/users/{target['id']}", json={"is_active": False}, headers=auth_header(admin_token)
    )

    response = client.get("/attendings", headers=auth_header(student_token))
    names = [a["full_name"] for a in response.json()]
    assert "Dr. Inactive" not in names


def test_attendings_require_authentication(client):
    assert client.get("/attendings").status_code == 401


def test_patient_token_can_list_attendings(client):
    """Patients are ordinary authenticated users now (a role, not a
    separate principal type), so GET /attendings -- open to any
    authenticated user -- doesn't reject them. They just can't set an
    attending when booking (see test_appointments_state_machine.py's
    test_patient_cannot_set_attending_room_equipment)."""
    student_token = register_and_login(client, "att-s4@example.com", role="student")
    _, patient_token = create_and_login_patient(client, student_token, "att-p4@example.com")

    response = client.get("/attendings", headers=auth_header(patient_token))
    assert response.status_code == 200
