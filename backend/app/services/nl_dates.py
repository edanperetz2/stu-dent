import re
from datetime import date, datetime, timedelta

from app.services.formatting import DISPLAY_TIMEZONE

TIME_OF_DAY_HOURS = {"morning": 9, "afternoon": 13, "evening": 17}

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def resolve_relative_date(phrase: str | None, *, now: datetime) -> date | None:
    """Resolve a short relative-day phrase ("tomorrow", "next friday") to a
    concrete date against `now`. Returns None for anything unrecognized.

    The model only ever supplies the phrase; this function does the actual
    date math, so it can never assert a wrong absolute date. `now` is
    converted to Asia/Jerusalem before any calendar-day math -- the app is
    Israel-only (see formatting.py), and a caller passing a UTC `now` would
    otherwise resolve "today"/"tomorrow" to the wrong day during the ~2-3h
    window each night between UTC midnight and Israel's own midnight.
    """
    if not phrase:
        return None
    normalized = phrase.strip().lower()
    local_now = now.astimezone(DISPLAY_TIMEZONE)

    if normalized == "today":
        return local_now.date()
    if normalized == "tomorrow":
        return (local_now + timedelta(days=1)).date()

    match = re.match(r"^(next\s+)?(\w+)$", normalized)
    if not match:
        return None
    has_next_prefix, day_name = match.groups()
    if day_name not in _WEEKDAYS:
        return None

    target_weekday = _WEEKDAYS[day_name]
    days_ahead = (target_weekday - local_now.weekday()) % 7
    if days_ahead == 0 and has_next_prefix:
        days_ahead = 7
    return (local_now + timedelta(days=days_ahead)).date()


def resolve_date_range(phrase: str | None, *, now: datetime) -> tuple[datetime, datetime] | None:
    """Resolve a short calendar-period phrase to a [start, end) datetime
    range, anchored to local (Asia/Jerusalem) midnight of the current day --
    same reasoning as resolve_relative_date. Used by the report assistant's
    periodic and ad-hoc paths. Returns None for anything unrecognized.
    """
    if not phrase:
        return None
    normalized = phrase.strip().lower()

    local_now = now.astimezone(DISPLAY_TIMEZONE)
    today_start = datetime(local_now.year, local_now.month, local_now.day, tzinfo=DISPLAY_TIMEZONE)

    if normalized in ("this week", "past week", "last 7 days"):
        return today_start - timedelta(days=7), today_start
    if normalized in ("last week", "previous week"):
        return today_start - timedelta(days=14), today_start - timedelta(days=7)
    if normalized in ("this month", "past month", "last 30 days"):
        return today_start - timedelta(days=30), today_start
    if normalized in ("last month", "previous month"):
        return today_start - timedelta(days=60), today_start - timedelta(days=30)

    return None
