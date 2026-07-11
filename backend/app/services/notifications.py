import uuid

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.realtime.events import publish
from app.services.email import send_email


def notify(
    db: Session,
    *,
    notification_type: NotificationType,
    message: str,
    recipient_id: uuid.UUID,
    related_appointment_id: uuid.UUID | None = None,
) -> Notification:
    """Stage a notification row on `db` without committing, best-effort
    email the recipient, and publish a real-time event for it.

    Callers are expected to commit alongside whatever primary write this
    notification documents, same convention as
    services/audit.py::record_audit_log.
    """
    entry = Notification(
        notification_type=notification_type,
        message=message,
        recipient_id=recipient_id,
        related_appointment_id=related_appointment_id,
    )
    db.add(entry)
    db.flush()

    recipient = db.get(User, recipient_id)
    if recipient is not None and recipient.email:
        subject = notification_type.value.replace("_", " ").title()
        send_email(to=recipient.email, subject=subject, body=message)

    publish(
        db,
        recipient_id=recipient_id,
        event={
            "event": "notification",
            "id": str(entry.id),
            "notification_type": notification_type.value,
            "message": message,
            "related_appointment_id": (
                str(related_appointment_id) if related_appointment_id is not None else None
            ),
        },
    )

    return entry
