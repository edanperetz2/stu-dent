from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.services.nl_dates import resolve_date_range, resolve_relative_date

ISRAEL = ZoneInfo("Asia/Jerusalem")


def test_tomorrow_uses_israel_calendar_day_not_utc():
    # 2026-01-15 22:30 UTC is already 2026-01-16 00:30 in Israel (IST, UTC+2
    # in January) -- the exact nightly window where naive UTC math resolves
    # "tomorrow" to the wrong day.
    now = datetime(2026, 1, 15, 22, 30, tzinfo=UTC)
    assert now.astimezone(ISRAEL).date() == datetime(2026, 1, 16).date()

    assert resolve_relative_date("today", now=now) == datetime(2026, 1, 16).date()
    assert resolve_relative_date("tomorrow", now=now) == datetime(2026, 1, 17).date()


def test_tomorrow_regular_daytime_utc_unaffected():
    now = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    assert resolve_relative_date("today", now=now) == datetime(2026, 1, 15).date()
    assert resolve_relative_date("tomorrow", now=now) == datetime(2026, 1, 16).date()


def test_next_weekday_uses_israel_calendar_day():
    # Same late-UTC-evening/already-next-day-in-Israel moment as above;
    # "friday" should resolve relative to Israel's Jan 16 (a Friday), not
    # UTC's Jan 15 (a Thursday).
    now = datetime(2026, 1, 15, 22, 30, tzinfo=UTC)
    assert resolve_relative_date("friday", now=now) == datetime(2026, 1, 16).date()


def test_resolve_date_range_anchors_to_israel_midnight():
    # 2026-01-15 22:30 UTC is 2026-01-16 00:30 in Israel -- "this week"
    # should be anchored to Jan 16's local midnight, not Jan 15's UTC one.
    now = datetime(2026, 1, 15, 22, 30, tzinfo=UTC)
    start, end = resolve_date_range("this week", now=now)
    assert end == datetime(2026, 1, 16, tzinfo=ISRAEL)
    assert start == datetime(2026, 1, 9, tzinfo=ISRAEL)


def test_resolve_relative_date_unrecognized_phrase_returns_none():
    now = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    assert resolve_relative_date("someday eventually", now=now) is None


def test_resolve_date_range_unrecognized_phrase_returns_none():
    now = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    assert resolve_date_range("someday eventually", now=now) is None
