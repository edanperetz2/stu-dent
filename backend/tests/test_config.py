import logging

from app.config import warn_if_placeholder_jwt_secret


def test_warns_when_jwt_secret_is_a_known_placeholder(caplog):
    with caplog.at_level(logging.WARNING, logger="app.config"):
        warn_if_placeholder_jwt_secret("change-me-please-generate-a-random-secret")

    assert any("JWT_SECRET_KEY" in record.message for record in caplog.records)


def test_no_warning_for_a_real_secret(caplog):
    with caplog.at_level(logging.WARNING, logger="app.config"):
        warn_if_placeholder_jwt_secret("a-genuinely-random-64-character-secret-nobody-could-guess")

    assert caplog.records == []
