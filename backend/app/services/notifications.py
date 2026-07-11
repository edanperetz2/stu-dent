import uuid

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType
from app.models.patient import Patient
from app.models.user import User
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
    """Stage a notification row on `db` without committing, and best-effort
    email the recipient (never blocks/fails the caller if that send fails).

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

    return entry
