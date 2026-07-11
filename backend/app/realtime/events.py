import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

CHANNEL = "stu_dent_events"


def publish(db: Session, *, recipient_id: uuid.UUID, event: dict[str, Any]) -> None:
    """Emit a Postgres NOTIFY carrying `event`.

    Postgres only delivers a NOTIFY once the current transaction actually
    commits, so a notification/message that gets rolled back never fires a
    phantom push -- this call can safely sit right after `db.add(...)` in
    the same transaction as the row it's announcing.
    """
    payload = {"recipient_id": str(recipient_id), **event}
    db.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": CHANNEL, "payload": json.dumps(payload)},
    )
