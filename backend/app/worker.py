import logging
import time

from app.config import settings
from app.database import SessionLocal
from app.jobs.expiry import expire_stale_appointments
from app.jobs.reminders import send_appointment_reminders
from app.jobs.reports import generate_scheduled_reports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_once() -> None:
    with SessionLocal() as db:
        sent = send_appointment_reminders(db)
        expired = expire_stale_appointments(db)
        reports = generate_scheduled_reports(db)
        if sent or expired or reports:
            logger.info(
                "worker pass: %d reminder(s) sent, %d appointment(s) expired, "
                "%d report(s) generated",
                sent,
                expired,
                reports,
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
