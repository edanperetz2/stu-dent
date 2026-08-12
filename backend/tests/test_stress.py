import threading

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User
from tests.conftest import engine as test_engine

# A session-per-call factory bound to the real test database (the same
# `engine` conftest.py's own fixtures use), NOT app.database.SessionLocal --
# that module-level engine is constructed from `settings.database_url` at
# import time, which happens before conftest.py overrides `DATABASE_URL` to
# point at the test DB, so it would otherwise silently write real requests
# into the dev database. Also NOT the `client`/`db_session` fixtures' single
# shared transaction, which would serialize every concurrent request onto
# one connection and hide the exact class of bug this file exists to catch.
_StressSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)


def _get_db_override():
    session = _StressSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _cleanup_users(*emails: str) -> None:
    session = _StressSessionLocal()
    try:
        user_ids = session.scalars(select(User.id).where(User.email.in_(emails))).all()
        # Registration/login write audit_log rows referencing these users
        # (actor_id and/or attempted_identifier) -- this project's own
        # soft-delete convention means users are never hard-deleted in real
        # code specifically because audit_log rows must never be orphaned,
        # so a real FK constraint blocks a bare user delete here too. Clear
        # the referencing rows first.
        session.query(AuditLog).filter(
            AuditLog.actor_id.in_(user_ids) | AuditLog.attempted_identifier.in_(emails)
        ).delete(synchronize_session=False)
        session.query(User).filter(User.email.in_(emails)).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def test_many_concurrent_registrations_are_all_handled_correctly_with_no_lost_writes():
    """Fires 25 simultaneous registration requests at the real app.

    Deliberately does NOT use the `client`/`db_session` fixtures every other
    test in this suite uses: those serialize all of a test's requests onto
    one shared transaction/connection, which would hide exactly the class of
    bug this test exists to catch. Here each thread's request gets its own
    real session/connection against the real test-database engine, matching
    how the app actually behaves under real concurrent traffic -- many
    simultaneous users hitting the same endpoint, per the course's manual
    "screw it up" test scenarios.
    """
    emails = [f"stress-user-{i}@example.com" for i in range(25)]
    results: list[int] = [0] * len(emails)

    app.dependency_overrides[get_db] = _get_db_override
    try:
        with TestClient(app) as real_client:

            def _register(index: int) -> None:
                response = real_client.post(
                    "/auth/register",
                    json={
                        "email": emails[index],
                        "password": "password123",
                        "full_name": f"Stress User {index}",
                        "role": "student",
                    },
                )
                results[index] = response.status_code

            threads = [threading.Thread(target=_register, args=(i,)) for i in range(len(emails))]
            try:
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

                # every request was handled cleanly -- no crash, no lost/duplicated write
                assert results == [201] * len(emails)

                # each concurrently-created account is independently usable, proving
                # the concurrent writes landed correctly rather than racing each
                # other away
                for email in emails:
                    login_response = real_client.post(
                        "/auth/login", json={"email": email, "password": "password123"}
                    )
                    assert login_response.status_code == 200
            finally:
                _cleanup_users(*emails)
    finally:
        app.dependency_overrides.clear()


def test_spamming_a_read_endpoint_concurrently_does_not_crash_the_app():
    """A cheap public endpoint hit by many simultaneous requests -- the
    literal "send 999999999 requests to some endpoint" scenario, scaled to
    something a test suite can run in a couple of seconds. Every response
    must come back 200; none may time out, hang, or 500.
    """
    results: list[int] = [0] * 50

    app.dependency_overrides[get_db] = _get_db_override
    try:
        with TestClient(app) as real_client:

            def _hit(index: int) -> None:
                results[index] = real_client.get("/health").status_code

            threads = [threading.Thread(target=_hit, args=(i,)) for i in range(len(results))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            assert results == [200] * len(results)
    finally:
        app.dependency_overrides.clear()
