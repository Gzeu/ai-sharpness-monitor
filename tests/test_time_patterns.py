"""Tests for time-based scoring."""
from datetime import datetime, timezone
from monitor.time_patterns import time_of_day_score, time_component_score


def dt(hour: int, weekday: int = 0) -> datetime:
    """Build a UTC datetime with given hour and weekday (0=Mon, 6=Sun)."""
    # Find a date with the right weekday: 2026-06-29 is Monday (weekday=0)
    base_monday = datetime(2026, 6, 29, hour, 0, 0, tzinfo=timezone.utc)
    days = (weekday - base_monday.weekday()) % 7
    from datetime import timedelta
    return base_monday + timedelta(days=days)


def test_weekend_scores_higher_than_weekday():
    sunday_3am = dt(3, weekday=6)
    monday_3pm = dt(15, weekday=0)
    assert time_of_day_score(sunday_3am) > time_of_day_score(monday_3pm)


def test_late_night_scores_higher_than_peak():
    night = dt(3, weekday=1)   # Tuesday 3am UTC
    peak = dt(18, weekday=1)   # Tuesday 6pm UTC (US+EU overlap)
    assert time_of_day_score(night) > time_of_day_score(peak)


def test_score_range_valid():
    for hour in range(24):
        for wd in range(7):
            s = time_of_day_score(dt(hour, wd))
            assert 0.0 <= s <= 1.0


def test_component_score_max_25():
    assert time_component_score() <= 25
    assert time_component_score() >= 0


def test_peak_overlap_lowest():
    """17-19 UTC weekday should be the worst window."""
    overlap = dt(18, weekday=2)   # Wednesday 18:00 UTC
    late = dt(2, weekday=2)       # Wednesday 02:00 UTC
    assert time_of_day_score(overlap) < time_of_day_score(late)
