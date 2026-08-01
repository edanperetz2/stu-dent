import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.password_reset_token import PasswordResetToken
from app.services import password_reset as password_reset_service
from tests.helpers import login, register


def _capture_reset_email(monkeypatch):
    """Replaces the service's send_email with a fake that records the
    outgoing message and extracts the raw token from the reset link --
    the only place the raw token is ever exposed (the DB only ever stores
    its hash, and the API response never reveals whether a token was
    minted at all).
    """
    captured: dict = {}

    def fake_send_email(*, to, subject, body):
        captured["to"] = to
        captured["subject"] = subject
        captured["body"] = body
        match = re.search(r"token=([\w-]+)", body)
        captured["token"] = match.group(1) if match else None

    monkeypatch.setattr(password_reset_service, "send_email", fake_send_email)
    return captured


def test_request_for_real_account_sends_email_with_a_working_token(client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)
    register(client, "reset1@example.com")

    response = client.post("/auth/password-reset/request", json={"email": "reset1@example.com"})

    assert response.status_code == 204
    assert captured["to"] == "reset1@example.com"
    assert captured["token"]


def test_request_for_unknown_email_still_returns_204_with_no_email_sent(client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)

    response = client.post("/auth/password-reset/request", json={"email": "nobody@example.com"})

    # The response gives no signal either way -- enumeration resistance --
    # but no email actually goes out for a nonexistent account.
    assert response.status_code == 204
    assert "to" not in captured


def test_confirm_changes_the_password(client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)
    register(client, "reset2@example.com")
    client.post("/auth/password-reset/request", json={"email": "reset2@example.com"})

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": captured["token"], "new_password": "newpassword456"},
    )
    assert response.status_code == 204

    assert login(client, "reset2@example.com", password="password123").status_code == 401
    assert login(client, "reset2@example.com", password="newpassword456").status_code == 200


def test_confirm_rejects_a_reused_token(client, monkeypatch):
    captured = _capture_reset_email(monkeypatch)
    register(client, "reset3@example.com")
    client.post("/auth/password-reset/request", json={"email": "reset3@example.com"})
    token = captured["token"]

    first = client.post(
        "/auth/password-reset/confirm", json={"token": token, "new_password": "newpassword456"}
    )
    assert first.status_code == 204

    second = client.post(
        "/auth/password-reset/confirm",
        json={"token": token, "new_password": "anotherpassword789"},
    )
    assert second.status_code == 400


def test_confirm_rejects_an_unknown_token(client):
    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "newpassword456"},
    )
    assert response.status_code == 400


def test_confirm_rejects_an_expired_token(client, monkeypatch, db_session):
    captured = _capture_reset_email(monkeypatch)
    register(client, "reset4@example.com")
    client.post("/auth/password-reset/request", json={"email": "reset4@example.com"})

    token_row = db_session.scalars(select(PasswordResetToken)).one()
    token_row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": captured["token"], "new_password": "newpassword456"},
    )
    assert response.status_code == 400


def test_request_is_rate_limited_per_email(client, monkeypatch):
    _capture_reset_email(monkeypatch)
    register(client, "reset5@example.com")

    for _ in range(5):
        client.post("/auth/password-reset/request", json={"email": "reset5@example.com"})

    response = client.post("/auth/password-reset/request", json={"email": "reset5@example.com"})
    assert response.status_code == 429
