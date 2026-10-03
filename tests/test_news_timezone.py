from datetime import date, datetime, timezone

from news.collector import NewsCollector, _parse_day_time_utc


def test_forexfactory_time_is_converted_from_eastern_to_utc():
    parsed = _parse_day_time_utc(date(2026, 9, 28), "8:30am")

    assert parsed == datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)


def test_invalid_forexfactory_time_returns_midnight_utc():
    parsed = _parse_day_time_utc(date(2026, 9, 28), "tentative")

    assert parsed == datetime(2026, 9, 28, tzinfo=timezone.utc)


def test_news_collector_defaults_to_eastern_source_timezone():
    assert NewsCollector().source_tz == "America/New_York"