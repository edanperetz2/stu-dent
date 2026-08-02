import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import Report, ReportPeriodType
from app.models.user import RoleEnum, User
from app.services.formatting import DISPLAY_TIMEZONE
from app.services.report_assistant import generate_periodic_report
from app.services.report_data import resource_utilization
from app.services.users import active_user_filters

logger = logging.getLogger(__name__)


def _period_bounds(period_type: ReportPeriodType, *, now: datetime) -> tuple[datetime, datetime]:
    # Anchored to the Israel-local calendar day, not raw UTC -- same
    # reasoning as nl_dates.py's resolve_relative_date/resolve_date_range:
    # a UTC calendar day is offset from Israel's own by 2-3 hours
    # (DST-dependent), so a raw-UTC boundary could recognize a new
    # week/month as started that many hours late or early relative to what
    # "this week"/"this month" actually means locally. The returned
    # datetimes are still precise, directly comparable/storable instants
    # (DISPLAY_TIMEZONE-aware, not naive) -- only which calendar day they
    # land on changes.
    local_now = now.astimezone(DISPLAY_TIMEZONE)
    today_start = datetime(local_now.year, local_now.month, local_now.day, tzinfo=DISPLAY_TIMEZONE)
    if period_type == ReportPeriodType.weekly:
        # Monday-aligned week, so every user's weekly report for a given
        # calendar week shares the same period_start -- that's what the
        # idempotency check below keys off.
        start = today_start - timedelta(days=today_start.weekday())
        return start, start + timedelta(days=7)

    start = today_start.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def generate_scheduled_reports(db: Session) -> int:
    """Generate this calendar week's/month's report for every active
    student/attending, once each. The existence check below is what
    throttles Ollama calls to once per user per period regardless of how
    often the worker polls -- no separate scheduling logic needed.
    """
    now = datetime.now(UTC)
    recipients = list(
        db.scalars(select(User).where(*active_user_filters(RoleEnum.student, RoleEnum.attending)))
    )

    generated = 0
    for period_type in (ReportPeriodType.weekly, ReportPeriodType.monthly):
        start, end = _period_bounds(period_type, now=now)

        # One query for the whole period/type, not one per recipient -- the
        # existence check still throttles Ollama calls to once per user per
        # period, just without a DB round trip per recipient to do it.
        already_generated = set(
            db.scalars(
                select(Report.recipient_id).where(
                    Report.period_type == period_type,
                    Report.period_start == start,
                )
            )
        )

        # resource_utilization is clinic-wide, not recipient-specific --
        # computed at most once per period_type here (lazily, only if
        # there's actually a recipient left needing a report) instead of
        # once per recipient inside generate_periodic_report.
        shared_resource_utilization: list[dict] | None = None

        for recipient in recipients:
            if recipient.id in already_generated:
                continue
            if shared_resource_utilization is None:
                shared_resource_utilization = resource_utilization(db, start=start, end=end)
            try:
                generate_periodic_report(
                    db,
                    recipient,
                    period_type=period_type,
                    period_start=start,
                    period_end=end,
                    resource_utilization_data=shared_resource_utilization,
                )
            except Exception:
                # One recipient's report failing (e.g. a malformed Ollama
                # response) must not block reports for everyone after them
                # in this pass -- idempotency means it's simply retried
                # next time the worker runs this job.
                logger.warning(
                    "Failed to generate %s report for user %s",
                    period_type.value,
                    recipient.id,
                    exc_info=True,
                )
                db.rollback()
                continue
            generated += 1

    return generated
