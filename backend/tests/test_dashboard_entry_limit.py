"""Regression tests for dashboard result-size validation."""
import pytest
from fastapi import HTTPException

from app.routers.dashboard import MAX_DASHBOARD_ENTRIES, _enforce_entry_limit


def test_dashboard_accepts_result_at_limit():
    rows = [{"id": index} for index in range(MAX_DASHBOARD_ENTRIES)]
    assert _enforce_entry_limit(rows) is rows


def test_dashboard_rejects_result_over_limit():
    rows = [{"id": index} for index in range(MAX_DASHBOARD_ENTRIES + 1)]
    with pytest.raises(HTTPException) as exc_info:
        _enforce_entry_limit(rows)
    assert exc_info.value.status_code == 413
    assert str(MAX_DASHBOARD_ENTRIES) in exc_info.value.detail
