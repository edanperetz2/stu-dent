from tests.helpers import auth_header, register_and_login


def test_student_can_access_own_dashboard_sample(client):
    token = register_and_login(client, "rbac-student1@example.com", role="student")
    response = client.get("/patients", headers=auth_header(token))
    assert response.status_code == 200


def test_attending_cannot_access_student_sample(client):
    token = register_and_login(client, "rbac-attending1@example.com", role="attending")
    response = client.get("/patients", headers=auth_header(token))
    assert response.status_code == 403


def test_attending_can_access_own_dashboard(client):
    token = register_and_login(client, "rbac-attending2@example.com", role="attending")
    response = client.get("/attending/dashboard", headers=auth_header(token))
    assert response.status_code == 200


def test_student_cannot_access_attending_dashboard(client):
    token = register_and_login(client, "rbac-student2@example.com", role="student")
    response = client.get("/attending/dashboard", headers=auth_header(token))
    assert response.status_code == 403


def test_admin_can_access_audit_log(client):
    token = register_and_login(client, "rbac-admin1@example.com", role="admin")
    response = client.get("/admin/audit-log", headers=auth_header(token))
    assert response.status_code == 200


def test_student_cannot_access_admin_audit_log(client):
    token = register_and_login(client, "rbac-student3@example.com", role="student")
    response = client.get("/admin/audit-log", headers=auth_header(token))
    assert response.status_code == 403


def test_attending_cannot_access_admin_audit_log(client):
    token = register_and_login(client, "rbac-attending3@example.com", role="attending")
    response = client.get("/admin/audit-log", headers=auth_header(token))
    assert response.status_code == 403


def test_no_token_rejected_on_protected_endpoints(client):
    assert client.get("/patients").status_code == 401
    assert client.get("/attending/dashboard").status_code == 401
    assert client.get("/admin/audit-log").status_code == 401
