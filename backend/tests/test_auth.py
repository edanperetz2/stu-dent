import jwt as pyjwt

from app.config import settings


def _register(
    client,
    email="student@example.com",
    password="password123",
    role="student",
    full_name="Stu Dent",
):
    return client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name, "role": role},
    )


def _login(client, email="student@example.com", password="password123"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_success(client):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "student@example.com"
    assert body["role"] == "student"
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_duplicate_email_rejected(client):
    assert _register(client).status_code == 201
    response = _register(client)
    assert response.status_code == 409


def test_register_accepts_each_role(client):
    for role in ("student", "attending", "admin"):
        response = _register(client, email=f"{role}@example.com", role=role)
        assert response.status_code == 201
        assert response.json()["role"] == role


def test_register_patient_without_owner_student_id_rejected(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "patient-no-owner@example.com",
            "password": "password123",
            "full_name": "No Owner",
            "role": "patient",
        },
    )
    assert response.status_code == 422


def test_register_non_patient_with_owner_student_id_rejected(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "student-with-owner@example.com",
            "password": "password123",
            "full_name": "Has Owner",
            "role": "student",
            "owner_student_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert response.status_code == 422


def test_login_success_returns_jwt_with_role(client):
    _register(client)
    response = _login(client)
    assert response.status_code == 200

    token = response.json()["access_token"]
    payload = pyjwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["role"] == "student"


def test_login_wrong_password_rejected(client):
    _register(client)
    response = _login(client, password="wrong-password")
    assert response.status_code == 401


def test_login_unknown_email_rejected(client):
    response = _login(client, email="nobody@example.com")
    assert response.status_code == 401


def test_users_me_requires_auth(client):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_users_me_returns_current_user(client):
    _register(client)
    token = _login(client).json()["access_token"]

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "student@example.com"


def test_users_me_update_requires_auth(client):
    response = client.patch("/users/me", json={"contact_phone": "555-1234"})
    assert response.status_code == 401


def test_users_me_update_sets_contact_phone_and_preferred_time(client):
    _register(client, email="prefs@example.com")
    token = _login(client, email="prefs@example.com").json()["access_token"]

    response = client.patch(
        "/users/me",
        json={"contact_phone": "555-1234", "preferred_time_of_day": "evening"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contact_phone"] == "555-1234"
    assert body["preferred_time_of_day"] == "evening"


def test_users_me_update_partial_leaves_other_field_untouched(client):
    _register(client, email="prefs2@example.com")
    token = _login(client, email="prefs2@example.com").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.patch("/users/me", json={"contact_phone": "555-1234"}, headers=headers)
    response = client.patch("/users/me", json={"preferred_time_of_day": "morning"}, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["contact_phone"] == "555-1234"
    assert body["preferred_time_of_day"] == "morning"
