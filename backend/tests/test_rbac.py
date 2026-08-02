from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings
from app.core.security import create_access_token
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


def test_token_with_non_uuid_subject_rejected_cleanly_not_500(client):
    # Regression test: a token whose `sub` claim isn't a real UUID (a
    # forged/corrupted token, only reachable if the JWT secret were ever
    # compromised) used to raise an unhandled ValueError from
    # uuid.UUID(user_id) -- a bare 500 -- instead of the same 401 every
    # other malformed-credentials path in get_current_user already returns.
    # create_access_token's `subject` param is typed as uuid.UUID, but
    # Python doesn't enforce that at runtime -- passing a plain string
    # reproduces exactly the malformed-token shape being guarded against.
    token = create_access_token(subject="not-a-real-uuid", role="student")
    response = client.get("/patients", headers=auth_header(token))
    assert response.status_code == 401


def test_token_with_non_string_subject_rejected_cleanly_not_500(client):
    # A non-string `sub` (int/list/dict) in a hand-forged token (same
    # compromised-secret premise as the test above) is rejected before it
    # ever reaches get_current_user's own uuid.UUID(user_id) call: PyJWT's
    # decode() enforces "sub must be a string" per RFC 7519 and raises
    # InvalidSubjectError -- a PyJWTError, already caught by _decode() into
    # the same clean 401. This guards that behavior directly, since it's a
    # framework guarantee this app relies on rather than re-validates.
    now = datetime.now(UTC)
    payload = {
        "sub": 12345,
        "role": "student",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    response = client.get("/patients", headers=auth_header(token))
    assert response.status_code == 401
