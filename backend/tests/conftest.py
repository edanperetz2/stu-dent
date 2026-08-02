import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import get_db
from app.main import app

_BACKEND_DIR = Path(__file__).resolve().parent.parent

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", settings.database_url.rsplit("/", 1)[0] + "/stu_dent_test"
)

# app.realtime.listener resolves its DSN via os.getenv("DATABASE_URL", ...)
# freshly at each app-lifespan startup (not the already-imported `settings`
# singleton), specifically so this override works: it must be set before
# any TestClient(app) triggers that startup, so the listener connects to
# the ephemeral test DB instead of the dev DB. Nothing else reads this env
# var directly, so this doesn't disturb the sync engine/settings used
# elsewhere in tests.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def _ensure_database_exists(url: str) -> None:
    base_url, db_name = url.rsplit("/", 1)
    admin_engine = create_engine(base_url + "/postgres", isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()


_ensure_database_exists(TEST_DATABASE_URL)

engine = create_engine(TEST_DATABASE_URL, future=True)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _run_alembic(*args: str) -> None:
    # A subprocess, not alembic's in-process Python API: alembic/env.py
    # resolves its DB URL via the already-imported `app.config.settings`
    # singleton, which was constructed above (`from app.config import
    # settings`) before TEST_DATABASE_URL was written into os.environ --
    # running in-process would silently target the dev DB instead of the
    # test DB. A fresh subprocess re-imports everything against the
    # now-correct os.environ, the same reasoning documented above for why
    # the realtime listener re-reads the env var fresh rather than trusting
    # the cached settings singleton.
    # `*args` is always a hardcoded literal from this file's own two call
    # sites ("upgrade", "head" / "downgrade", "base") -- never external
    # input, despite ruff's S603 not being able to prove that statically.
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args], cwd=_BACKEND_DIR, check=True
    )


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    # Runs the real Alembic migration chain against the test DB (matching
    # what CI does) instead of Base.metadata.create_all() -- create_all()
    # builds a schema straight from the current ORM models, which means a
    # model change shipped without (or with a wrong) matching migration was
    # previously invisible in every local test run, only ever surfacing in
    # CI. This project's own "one Alembic migration per schema change, no
    # exceptions" convention now gets enforced locally too.
    _run_alembic("upgrade", "head")
    yield
    _run_alembic("downgrade", "base")


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        # In a `finally`, not just after the `with` block: if
        # TestClient(app).__enter__() itself raises (e.g. the app's
        # lifespan startup fails), this generator never reaches `yield`,
        # so pytest never resumes it for teardown -- the override would
        # otherwise leak into whichever test runs next.
        app.dependency_overrides.clear()
