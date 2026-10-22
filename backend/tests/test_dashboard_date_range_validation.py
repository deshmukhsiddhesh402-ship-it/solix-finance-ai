"""Regression tests for dashboard reporting date-range validation."""
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.routers.dashboard import MAX_DASHBOARD_RANGE_DAYS, _date_range


def test_date_range_accepts_normal_range():
    start, end = _date_range(date(2026, 1, 1), date(2026, 1, 31))
    assert start == date(2026, 1, 1)
    assert end == date(2026, 1, 31)


def test_date_range_accepts_maximum_allowed_window():
    end = date(2026, 10, 22)
    start = end - timedelta(days=MAX_DASHBOARD_RANGE_DAYS)
    assert _date_range(start, end) == (start, end)


def test_date_range_rejects_reversed_dates():
    with pytest.raises(HTTPException) as exc_info:
        _date_range(date(2026, 2, 1), date(2026, 1, 1))
    assert exc_info.value.status_code == 400
    assert "on or before" in exc_info.value.detail


def test_date_range_rejects_window_over_maximum():
    end = date(2026, 10, 22)
    start = end - timedelta(days=MAX_DASHBOARD_RANGE_DAYS + 1)
    with pytest.raises(HTTPException) as exc_info:
        _date_range(start, end)
    assert exc_info.value.status_code == 400
    assert str(MAX_DASHBOARD_RANGE_DAYS) in exc_info.value.detail


def test_date_range_defaults_to_recent_180_days():
    end = date(2026, 10, 22)
    start, actual_end = _date_range(None, end)
    assert actual_end == end
    assert start == end - timedelta(days=180)
