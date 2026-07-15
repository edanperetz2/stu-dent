import logging
import time

from app.config import settings
from app.database import SessionLocal
from app.jobs.expiry import expire_stale_appointments
from app.jobs.feedback_reminders import notify_pending_feedback
from app.jobs.reactivation import reactivate_expired_deactivations
from app.jobs.reminders import send_appointment_reminders
from app.jobs.reports import generate_scheduled_reports
from app.jobs.unresolved_appointments import notify_unresolved_past_appointments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_once() -> None:
    with SessionLocal() as db:
        sent = send_appointment_reminders(db)
        expired = expire_stale_appointments(db)
        reports = generate_scheduled_reports(db)
        reactivated = reactivate_expired_deactivations(db)
        unresolved_nagged = notify_unresolved_past_appointments(db)
        feedback_nagged = notify_pending_feedback(db)
        if sent or expired or reports or reactivated or unresolved_nagged or feedback_nagged:
            logger.info(
                "worker pass: %d reminder(s) sent, %d appointment(s) expired, "
                "%d report(s) generated, %d resource(s) reactivated, "
                "%d unresolved-appointment nag(s) sent, %d feedback nag(s) sent",
                sent,
                expired,
                reports,
                reactivated,
                unresolved_nagged,
                feedback_nagged,
            )


def main() -> None:
    logger.info(
        "Stu-Dent background worker starting, polling every %ds",
        settings.job_poll_interval_seconds,
    )
    while True:
        run_once()
        time.sleep(settings.job_poll_interval_seconds)


if __name__ == "__main__":
    main()
