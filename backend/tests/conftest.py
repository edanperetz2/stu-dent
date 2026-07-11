import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app

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


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    with engine.begin() as conn:
        # Base.metadata.create_all() never creates extensions; the
        # appointments table's exclusion constraints need this for GiST
        # indexes over plain-equality (UUID) columns.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
