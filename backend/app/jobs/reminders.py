from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import NotificationType
from app.services.notifications import notify


def send_appointment_reminders(db: Session) -> int:
    """Send a one-time reminder for confirmed appointments starting soon.

    Only `confirmed` appointments qualify; `reminder_sent_at` guards against
    re-sending on the next poll. Commits per appointment so one bad row
    doesn't block the rest of the batch.
    """
    now = datetime.now(UTC)
    window_end = now + timedelta(hours=settings.reminder_lead_hours)

    candidates = list(
        db.scalars(
            select(Appointment).where(
                Appointment.status == AppointmentStatus.confirmed,
                Appointment.reminder_sent_at.is_(None),
                Appointment.start_time > now,
                Appointment.start_time <= window_end,
            )
        )
    )

    sent = 0
    for appointment in candidates:
        message = (
            f"Reminder: you have an appointment scheduled for "
            f"{appointment.start_time.isoformat()}."
        )
        notify(
            db,
            notification_type=NotificationType.appointment_reminder,
            message=message,
            recipient_user_id=appointment.student_id,
            related_appointment_id=appointment.id,
        )
        notify(
            db,
            notification_type=NotificationType.appointment_reminder,
            message=message,
            recipient_patient_id=appointment.patient_id,
            related_appointment_id=appointment.id,
        )
        if appointment.attending_id is not None:
            notify(
                db,
                notification_type=NotificationType.appointment_reminder,
                message=message,
                recipient_user_id=appointment.attending_id,
                related_appointment_id=appointment.id,
            )

        appointment.reminder_sent_at = now
        db.commit()
        sent += 1

    return sent
