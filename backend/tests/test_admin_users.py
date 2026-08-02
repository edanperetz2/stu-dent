import uuid

from tests.helpers import auth_header, login, register, register_and_login


def _get_user_id(client, admin_token, email):
    users = client.get("/admin/users", headers=auth_header(admin_token)).json()
    return next(u["id"] for u in users if u["email"] == email)


def test_admin_can_view_user_detail(client):
    admin_token = register_and_login(client, "admusr-admin1@example.com", role="admin")
    register(client, "admusr-target1@example.com", role="student")
    user_id = _get_user_id(client, admin_token, "admusr-target1@example.com")

    response = client.get(f"/admin/users/{user_id}", headers=auth_header(admin_token))
    assert response.status_code == 200
    assert response.json()["email"] == "admusr-target1@example.com"


def test_non_admin_cannot_view_user_detail(client):
    student_token = register_and_login(client, "admusr-student1@example.com", role="student")
    response = client.get(f"/admin/users/{uuid.uuid4()}", headers=auth_header(student_token))
    assert response.status_code == 403


def test_admin_can_delete_another_user(client):
    admin_token = register_and_login(client, "admusr-admin2@example.com", role="admin")
    register(client, "admusr-target2@example.com", role="student")
    user_id = _get_user_id(client, admin_token, "admusr-target2@example.com")

    delete_response = client.delete(f"/admin/users/{user_id}", headers=auth_header(admin_token))
    assert delete_response.status_code == 204

    detail_response = client.get(f"/admin/users/{user_id}", headers=auth_header(admin_token))
    assert detail_response.status_code == 404

    list_response = client.get("/admin/users", headers=auth_header(admin_token))
    assert all(u["email"] != "admusr-target2@example.com" for u in list_response.json())


def test_deleted_user_token_stops_working(client):
    admin_token = register_and_login(client, "admusr-admin3@example.com", role="admin")
    target_token = register_and_login(client, "admusr-target3@example.com", role="student")
    user_id = _get_user_id(client, admin_token, "admusr-target3@example.com")

    client.delete(f"/admin/users/{user_id}", headers=auth_header(admin_token))

    response = client.get("/users/me", headers=auth_header(target_token))
    assert response.status_code == 401

    login_response = login(client, "admusr-target3@example.com")
    assert login_response.status_code == 401


def test_admin_cannot_delete_own_account(client):
    admin_token = register_and_login(client, "admusr-admin4@example.com", role="admin")
    admin_id = _get_user_id(client, admin_token, "admusr-admin4@example.com")

    response = client.delete(f"/admin/users/{admin_id}", headers=auth_header(admin_token))
    assert response.status_code == 400


def test_admin_cannot_change_own_role(client):
    admin_token = register_and_login(client, "admusr-admin6@example.com", role="admin")
    admin_id = _get_user_id(client, admin_token, "admusr-admin6@example.com")

    response = client.patch(
        f"/admin/users/{admin_id}", json={"role": "student"}, headers=auth_header(admin_token)
    )
    assert response.status_code == 400

    # The rejected request must not have partially applied before raising.
    still_admin = client.get(f"/admin/users/{admin_id}", headers=auth_header(admin_token))
    assert still_admin.json()["role"] == "admin"


def test_admin_cannot_role_flip_a_user_into_patient(client):
    admin_token = register_and_login(client, "admusr-admin8@example.com", role="admin")
    register(client, "admusr-target8@example.com", role="student")
    user_id = _get_user_id(client, admin_token, "admusr-target8@example.com")

    response = client.patch(
        f"/admin/users/{user_id}", json={"role": "patient"}, headers=auth_header(admin_token)
    )
    assert response.status_code == 422

    still_student = client.get(f"/admin/users/{user_id}", headers=auth_header(admin_token))
    assert still_student.json()["role"] == "student"


def test_admin_cannot_role_flip_a_patient_away_from_patient(client):
    admin_token = register_and_login(client, "admusr-admin9@example.com", role="admin")
    student_token = register_and_login(client, "admusr-student9@example.com", role="student")
    student_id = _get_user_id(client, admin_token, "admusr-student9@example.com")
    client.post(
        "/patients",
        json={
            "full_name": "Target Patient",
            "email": "admusr-patient9@example.com",
            "password": "password123",
        },
        headers=auth_header(student_token),
    )
    patient_id = _get_user_id(client, admin_token, "admusr-patient9@example.com")

    response = client.patch(
        f"/admin/users/{patient_id}", json={"role": "student"}, headers=auth_header(admin_token)
    )
    assert response.status_code == 422

    still_patient = client.get(f"/admin/users/{patient_id}", headers=auth_header(admin_token))
    assert still_patient.json()["role"] == "patient"
    # is_active-only updates on the same user must still work -- only the
    # role field is blocked, not the whole route for this user.
    assert (
        client.patch(
            f"/admin/users/{patient_id}",
            json={"is_active": False},
            headers=auth_header(admin_token),
        ).status_code
        == 200
    )
    assert student_id != patient_id


def test_admin_cannot_deactivate_own_account_via_patch(client):
    admin_token = register_and_login(client, "admusr-admin7@example.com", role="admin")
    admin_id = _get_user_id(client, admin_token, "admusr-admin7@example.com")

    response = client.patch(
        f"/admin/users/{admin_id}", json={"is_active": False}, headers=auth_header(admin_token)
    )
    assert response.status_code == 400

    still_active = client.get(f"/admin/users/{admin_id}", headers=auth_header(admin_token))
    assert still_active.json()["is_active"] is True


def test_non_admin_cannot_delete_user(client):
    student_token = register_and_login(client, "admusr-student2@example.com", role="student")
    admin_token = register_and_login(client, "admusr-admin5@example.com", role="admin")
    register(client, "admusr-target4@example.com", role="student")
    user_id = _get_user_id(client, admin_token, "admusr-target4@example.com")

    response = client.delete(f"/admin/users/{user_id}", headers=auth_header(student_token))
    assert response.status_code == 403
