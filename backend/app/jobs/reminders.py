import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.appointment import Appointment, AppointmentStatus
from app.models.notification import NotificationType
from app.services.formatting import format_dt
from app.services.notifications import notify

logger = logging.getLogger(__name__)


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
        try:
            message = (
                f"Reminder: you have an appointment scheduled for "
                f"{format_dt(appointment.start_time)}."
            )
            notify(
                db,
                notification_type=NotificationType.appointment_reminder,
                message=message,
                recipient_id=appointment.student_id,
                related_appointment_id=appointment.id,
            )
            notify(
                db,
                notification_type=NotificationType.appointment_reminder,
                message=message,
                recipient_id=appointment.patient_id,
                related_appointment_id=appointment.id,
            )
            if appointment.attending_id is not None:
                notify(
                    db,
                    notification_type=NotificationType.appointment_reminder,
                    message=message,
                    recipient_id=appointment.attending_id,
                    related_appointment_id=appointment.id,
                )

            appointment.reminder_sent_at = now
            db.commit()
        except Exception:
            # One appointment failing to notify must not block reminders for
            # the rest of the batch -- reminder_sent_at is only ever set
            # after a successful commit, so a failed row is simply retried
            # next time this job runs.
            logger.warning(
                "Failed to send reminder for appointment %s", appointment.id, exc_info=True
            )
            db.rollback()
            continue
        sent += 1

    return sent
