from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.report import Report, ReportPeriodType
from app.models.user import RoleEnum, User
from app.services.report_assistant import generate_periodic_report


def _period_bounds(period_type: ReportPeriodType, *, now: datetime) -> tuple[datetime, datetime]:
    today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)
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
        db.scalars(
            select(User).where(
                User.role.in_((RoleEnum.student, RoleEnum.attending)),
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
    )

    generated = 0
    for period_type in (ReportPeriodType.weekly, ReportPeriodType.monthly):
        start, end = _period_bounds(period_type, now=now)
        for recipient in recipients:
            existing = db.scalar(
                select(Report).where(
                    Report.recipient_id == recipient.id,
                    Report.period_type == period_type,
                    Report.period_start == start,
                )
            )
            if existing is not None:
                continue
            generate_periodic_report(
                db, recipient, period_type=period_type, period_start=start, period_end=end
            )
            generated += 1

    return generated
