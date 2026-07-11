from tests.helpers import auth_header, register_and_login


def test_students_list_is_public(client):
    register_and_login(client, "stu-list-1@example.com", role="student", full_name="Dr. Nobody")
    response = client.get("/students")
    assert response.status_code == 200
    names = [s["full_name"] for s in response.json()]
    assert "Dr. Nobody" in names
    # Public shape only: no email, no role, no other user fields leaked.
    assert set(response.json()[0].keys()) == {"id", "full_name"}


def test_students_list_excludes_non_students(client):
    register_and_login(client, "stu-list-2@example.com", role="student", full_name="Real Student")
    register_and_login(
        client, "stu-list-2b@example.com", role="attending", full_name="An Attending"
    )
    register_and_login(client, "stu-list-2c@example.com", role="admin", full_name="An Admin")

    names = [s["full_name"] for s in client.get("/students").json()]
    assert "Real Student" in names
    assert "An Attending" not in names
    assert "An Admin" not in names


def test_students_list_excludes_inactive(client):
    admin_token = register_and_login(client, "stu-list-3admin@example.com", role="admin")
    register_and_login(
        client, "stu-list-3@example.com", role="student", full_name="Inactive Student"
    )

    users = client.get("/admin/users", headers=auth_header(admin_token)).json()
    target = next(u for u in users if u["full_name"] == "Inactive Student")
    client.patch(
        f"/admin/users/{target['id']}", json={"is_active": False}, headers=auth_header(admin_token)
    )

    names = [s["full_name"] for s in client.get("/students").json()]
    assert "Inactive Student" not in names
