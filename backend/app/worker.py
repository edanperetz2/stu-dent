import logging
import time

from app.config import settings
from app.database import SessionLocal
from app.jobs.expiry import expire_stale_appointments
from app.jobs.reminders import send_appointment_reminders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_once() -> None:
    with SessionLocal() as db:
        sent = send_appointment_reminders(db)
        expired = expire_stale_appointments(db)
        if sent or expired:
            logger.info(
                "worker pass: %d reminder(s) sent, %d appointment(s) expired", sent, expired
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
