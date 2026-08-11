from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.nl_dates import resolve_date_range, resolve_relative_date
from tests.helpers import relative_datetime

ISRAEL = ZoneInfo("Asia/Jerusalem")


def test_tomorrow_uses_israel_calendar_day_not_utc():
    # Late UTC evening is already the next calendar day in Israel -- the
    # exact nightly window where naive UTC math resolves "tomorrow" wrong.
    now = relative_datetime(days=0, hour=22, minute=30)
    local_day = now.astimezone(ISRAEL).date()
    assert local_day == now.date() + timedelta(days=1)

    assert resolve_relative_date("today", now=now) == local_day
    assert resolve_relative_date("tomorrow", now=now) == local_day + timedelta(days=1)


def test_tomorrow_regular_daytime_utc_unaffected():
    now = relative_datetime(days=0, hour=8)
    local_day = now.astimezone(ISRAEL).date()
    assert local_day == now.date()
    assert resolve_relative_date("today", now=now) == local_day
    assert resolve_relative_date("tomorrow", now=now) == local_day + timedelta(days=1)


def test_next_weekday_uses_israel_calendar_day():
    # Pick the next late-UTC Thursday. Israel is already on Friday, so the
    # weekday resolver must use that local day rather than UTC Thursday.
    candidate = relative_datetime(days=0, hour=22, minute=30)
    now = candidate + timedelta(days=(3 - candidate.weekday()) % 7)
    local_day = now.astimezone(ISRAEL).date()
    assert local_day.weekday() == 4
    assert resolve_relative_date("friday", now=now) == local_day


def test_resolve_date_range_anchors_to_israel_midnight():
    now = relative_datetime(days=0, hour=22, minute=30)
    local_midnight = datetime.combine(now.astimezone(ISRAEL).date(), time.min, tzinfo=ISRAEL)
    start, end = resolve_date_range("this week", now=now)
    assert end == local_midnight
    assert start == local_midnight - timedelta(days=7)


def test_resolve_relative_date_unrecognized_phrase_returns_none():
    now = relative_datetime(days=0, hour=8)
    assert resolve_relative_date("someday eventually", now=now) is None


def test_resolve_date_range_unrecognized_phrase_returns_none():
    now = relative_datetime(days=0, hour=8)
    assert resolve_date_range("someday eventually", now=now) is None
