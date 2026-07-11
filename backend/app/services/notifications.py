import uuid

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.patient import Patient
from app.models.user import User
from app.realtime.events import publish
from app.services.email import send_email


def notify(
    db: Session,
    *,
    notification_type: NotificationType,
    message: str,
    recipient_user_id: uuid.UUID | None = None,
    recipient_patient_id: uuid.UUID | None = None,
    related_appointment_id: uuid.UUID | None = None,
) -> Notification:
    """Stage a notification row on `db` without committing, best-effort
    email the recipient, and publish a real-time event for it.

    Exactly one of recipient_user_id/recipient_patient_id must be set (the
    model's CheckConstraint enforces this at the DB level too). Callers are
    expected to commit alongside whatever primary write this notification
    documents, same convention as services/audit.py::record_audit_log.
    """
    entry = Notification(
        notification_type=notification_type,
        message=message,
        recipient_user_id=recipient_user_id,
        recipient_patient_id=recipient_patient_id,
        related_appointment_id=related_appointment_id,
    )
    db.add(entry)
    db.flush()

    recipient_email = None
    if recipient_user_id is not None:
        user = db.get(User, recipient_user_id)
        recipient_email = user.email if user else None
    elif recipient_patient_id is not None:
        patient = db.get(Patient, recipient_patient_id)
        recipient_email = patient.email if patient else None

    if recipient_email:
        subject = notification_type.value.replace("_", " ").title()
        send_email(to=recipient_email, subject=subject, body=message)

    kind, recipient_id = (
        ("user", recipient_user_id)
        if recipient_user_id is not None
        else ("patient", recipient_patient_id)
    )
    publish(
        db,
        kind=kind,
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
