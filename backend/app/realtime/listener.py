import asyncio
import json
import logging
import os

import psycopg

from app.config import settings
from app.realtime.events import CHANNEL
from app.realtime.manager import manager

logger = logging.getLogger(__name__)

_RECONNECT_DELAY_SECONDS = 5


def _resolve_dsn() -> str:
    """Read fresh at call time, not a cached `settings` value.

    This is what makes the listener testable: `tests/conftest.py` sets
    `os.environ["DATABASE_URL"]` to the ephemeral test DB before any
    `TestClient` triggers app startup, so this picks up the test DB even
    though `settings.database_url` (read once at import time) stays pointed
    at the dev DB throughout the test session.
    """
    raw = os.getenv("DATABASE_URL", settings.database_url)
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


async def _listen_once() -> None:
    dsn = _resolve_dsn()
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        await conn.execute(f"LISTEN {CHANNEL}")
        logger.info("Realtime listener connected, listening on %r", CHANNEL)
        async for notification in conn.notifies():
            try:
                payload = json.loads(notification.payload)
                await manager.send_to(payload["kind"], payload["recipient_id"], payload)
            except Exception:
                logger.warning("Failed to relay a realtime event", exc_info=True)


async def listen_forever() -> None:
    """Runs until cancelled, reconnecting on any connection-level failure so
    a transient DB blip doesn't permanently kill real-time push for the rest
    of the process's life.
    """
    while True:
        try:
            await _listen_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Realtime listener connection lost, retrying", exc_info=True)
            await asyncio.sleep(_RECONNECT_DELAY_SECONDS)
