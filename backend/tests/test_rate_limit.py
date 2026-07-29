import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.core.rate_limit import enforce_login_rate_limit, enforce_registration_rate_limit
from app.models.audit_log import AuditLog
from app.services.audit import record_audit_log
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
    # user_register_attempt is recorded under the real email now too (see
    # enforce_registration_rate_limit's per-email dimension), so it shares
    # this identifier with the login rows.
    assert actions == {"user_register_attempt", "user_login_failure", "user_login_success"}


def _write_failures(db_session, *, identifier, ip_address, action, count):
    for _ in range(count):
        record_audit_log(
            db_session, action=action, attempted_identifier=identifier, ip_address=ip_address
        )
    db_session.commit()


def test_login_rate_limit_is_scoped_per_ip_not_just_identifier(db_session):
    """Regression test: the same identifier failing from a DIFFERENT IP
    must not be blocked by another IP's failures against it -- that was
    exactly the false-positive-lockout bug this dimension fixes (anyone
    who merely knew a victim's email could lock their real account out
    from anywhere).
    """
    _write_failures(
        db_session,
        identifier="shared-target@example.com",
        ip_address="10.0.0.1",
        action="user_login_failure",
        count=settings.login_rate_limit_max_attempts,
    )

    # The attacker's own IP is now blocked...
    with pytest.raises(HTTPException) as exc_info:
        enforce_login_rate_limit(
            db_session,
            identifier="shared-target@example.com",
            ip_address="10.0.0.1",
            failure_action="user_login_failure",
        )
    assert exc_info.value.status_code == 429

    # ...but the real account holder, logging in from a different IP, is
    # completely unaffected.
    enforce_login_rate_limit(
        db_session,
        identifier="shared-target@example.com",
        ip_address="10.0.0.2",
        failure_action="user_login_failure",
    )


def test_registration_rate_limit_per_email_does_not_block_other_emails_same_ip(db_session):
    """A shared classroom/clinic IP with many *different* real registrants
    must not get bunched into one tight counter -- only repeated attempts
    at the *same* email should trip the low per-email threshold.
    """
    _write_failures(
        db_session,
        identifier="probed-target@example.com",
        ip_address="10.0.0.5",
        action="user_register_attempt",
        count=settings.registration_rate_limit_max_attempts,
    )

    with pytest.raises(HTTPException) as exc_info:
        enforce_registration_rate_limit(
            db_session, email="probed-target@example.com", ip_address="10.0.0.5"
        )
    assert exc_info.value.status_code == 429

    # A different real person registering a different email from the same
    # IP is not blocked by the probed target's own counter.
    enforce_registration_rate_limit(
        db_session, email="someone-else@example.com", ip_address="10.0.0.5"
    )


def test_registration_rate_limit_per_ip_ceiling_catches_a_mass_flood(db_session):
    """Even though many *different* emails from one IP don't trip the
    per-email check, a genuine mass-registration flood from one IP must
    still eventually hit the higher per-IP-only ceiling.
    """
    for i in range(settings.registration_rate_limit_max_attempts_per_ip):
        record_audit_log(
            db_session,
            action="user_register_attempt",
            attempted_identifier=f"flood-{i}@example.com",
            ip_address="10.0.0.9",
        )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        enforce_registration_rate_limit(
            db_session, email="one-more@example.com", ip_address="10.0.0.9"
        )
    assert exc_info.value.status_code == 429

    # A different IP entirely is unaffected by this IP's flood.
    enforce_registration_rate_limit(
        db_session, email="one-more@example.com", ip_address="10.0.0.10"
    )
