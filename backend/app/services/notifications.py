import uuid

from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationType


def notify(
    db: Session,
    *,
    notification_type: NotificationType,
    message: str,
    recipient_user_id: uuid.UUID | None = None,
    recipient_patient_id: uuid.UUID | None = None,
    related_appointment_id: uuid.UUID | None = None,
) -> Notification:
    """Stage a notification row on `db` without committing.

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
    return entry
