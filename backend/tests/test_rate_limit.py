from sqlalchemy import select

from app.config import settings
from app.models.audit_log import AuditLog
from tests.helpers import create_patient, register, register_and_login


def test_login_locks_out_after_max_failed_attempts(client):
    register(client, "ratelimit1@example.com")

    for _ in range(settings.login_rate_limit_max_attempts):
        response = client.post(
            "/auth/login", json={"email": "ratelimit1@example.com", "password": "wrong-password"}
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login", json={"email": "ratelimit1@example.com", "password": "wrong-password"}
    )
    assert blocked.status_code == 429

    still_blocked_with_correct_password = client.post(
        "/auth/login", json={"email": "ratelimit1@example.com", "password": "password123"}
    )
    assert still_blocked_with_correct_password.status_code == 429


def test_rate_limit_is_scoped_per_identifier(client):
    register(client, "ratelimit2@example.com")
    register(client, "ratelimit3@example.com")

    for _ in range(settings.login_rate_limit_max_attempts):
        client.post(
            "/auth/login", json={"email": "ratelimit2@example.com", "password": "wrong-password"}
        )

    unaffected = client.post(
        "/auth/login", json={"email": "ratelimit3@example.com", "password": "password123"}
    )
    assert unaffected.status_code == 200


def test_patient_login_is_rate_limited_independently(client):
    student_token = register_and_login(client, "ratelimit-student@example.com", role="student")
    create_patient(
        client,
        student_token,
        full_name="Rate Limited Patient",
        email="ratelimit-patient@example.com",
        password="patientpass123",
    )

    for _ in range(settings.login_rate_limit_max_attempts):
        response = client.post(
            "/auth/login",
            json={"email": "ratelimit-patient@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login",
        json={"email": "ratelimit-patient@example.com", "password": "wrong-password"},
    )
    assert blocked.status_code == 429

    # the student's own login is unaffected by their patient's lockout
    still_ok = client.post(
        "/auth/login", json={"email": "ratelimit-student@example.com", "password": "password123"}
    )
    assert still_ok.status_code == 200


def test_login_attempts_write_audit_log_rows(client, db_session):
    register(client, "audit-login@example.com")
    client.post(
        "/auth/login", json={"email": "audit-login@example.com", "password": "wrong-password"}
    )
    client.post("/auth/login", json={"email": "audit-login@example.com", "password": "password123"})

    actions = {
        row.action
        for row in db_session.scalars(
            select(AuditLog).where(AuditLog.attempted_identifier == "audit-login@example.com")
        ).all()
    }
    assert actions == {"user_login_failure", "user_login_success"}
