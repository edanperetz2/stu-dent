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

# Reactivation runs first: expiry (and the waitlist recheck it triggers)
# checks room/equipment is_active, so a resource whose scheduled
# deactivation lapses this same tick must already be reactivated before
# expiry's recheck runs, or a waitlist entry waiting on it would be
# wrongly treated as still blocked for another full poll interval.
_JOBS: list[tuple[str, str]] = [
    ("resource(s) reactivated", "reactivate_expired_deactivations"),
    ("reminder(s) sent", "send_appointment_reminders"),
    ("appointment(s) expired", "expire_stale_appointments"),
    ("report(s) generated", "generate_scheduled_reports"),
    ("unresolved-appointment nag(s) sent", "notify_unresolved_past_appointments"),
    ("feedback nag(s) sent", "notify_pending_feedback"),
]
_JOB_FUNCS = {
    "reactivate_expired_deactivations": reactivate_expired_deactivations,
    "send_appointment_reminders": send_appointment_reminders,
    "expire_stale_appointments": expire_stale_appointments,
    "generate_scheduled_reports": generate_scheduled_reports,
    "notify_unresolved_past_appointments": notify_unresolved_past_appointments,
    "notify_pending_feedback": notify_pending_feedback,
}


def run_once() -> None:
    with SessionLocal() as db:
        summary: list[str] = []
        for label, func_name in _JOBS:
            try:
                count = _JOB_FUNCS[func_name](db)
            except Exception:
                # One job's bug/DB hiccup must not block every other job on
                # this tick (or, via main()'s loop, every future tick --
                # this used to be entirely unhandled, so any exception here
                # killed the whole worker process with nothing left running
                # reminders/expiry/waitlist-promotion/reactivation/feedback
                # nags ever again).
                logger.exception("worker job %s failed, continuing with the rest", func_name)
                db.rollback()
                continue
            if count:
                summary.append(f"{count} {label}")
        if summary:
            logger.info("worker pass: %s", ", ".join(summary))


def main() -> None:
    logger.info(
        "Stu-Dent background worker starting, polling every %ds",
        settings.job_poll_interval_seconds,
    )
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("worker pass failed outside any single job, retrying next interval")
        time.sleep(settings.job_poll_interval_seconds)


if __name__ == "__main__":
    main()
