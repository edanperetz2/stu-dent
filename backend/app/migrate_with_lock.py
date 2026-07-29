"""Runs `alembic upgrade head` guarded by a Postgres advisory lock.

Both `api` and `worker` build from this same image and each ran a bare
`alembic upgrade head` before starting their real process (see
entrypoint.sh). On a genuinely fresh database (first `docker compose up`)
they only depend on `db: service_healthy`, not on each other, so both
start together and race to migrate the empty schema concurrently --
duplicate `CREATE TABLE`/`CREATE TYPE`/`INSERT INTO alembic_version`
attempts, and the loser's container exits nonzero.

The advisory lock is purely a coordination primitive: it's held on one
dedicated connection while `alembic upgrade head` runs as a subprocess
(its own connection(s), unchanged from before), so whichever container
gets here first fully finishes migrating before the second one even
starts the CLI.
"""

import logging
import os
import subprocess
import sys

import psycopg

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Arbitrary constant -- only needs to be the same across every process
# that might race, not meaningful beyond being unique to this app's
# migration step.
_MIGRATION_LOCK_KEY = 837462910


def _resolve_dsn() -> str:
    from app.config import settings

    # Same override-for-tests idiom as realtime/listener.py::_resolve_dsn.
    raw = os.getenv("DATABASE_URL", settings.database_url)
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    dsn = _resolve_dsn()
    with psycopg.connect(dsn, autocommit=True) as conn:
        logger.info("Waiting for the migration lock...")
        conn.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_KEY,))
        logger.info("Migration lock acquired, running alembic upgrade head")
        try:
            subprocess.run(["alembic", "upgrade", "head"], check=True)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_KEY,))


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
