"""Regression tests for dashboard result-size validation."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import dashboard
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


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.limit_value = None

    def join(self, *args):
        return self

    def filter(self, *args):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self, query):
        self.query_result = query

    def query(self, *args):
        return self.query_result


def test_load_entries_applies_database_limit_and_rejects_overflow(monkeypatch):
    monkeypatch.setattr(dashboard, "MAX_DASHBOARD_ENTRIES", 2)
    rows = [
        (date(2026, 11, 1), "Cash", "asset", 10.0, 0.0),
        (date(2026, 11, 2), "Capital", "equity", 0.0, 10.0),
        (date(2026, 11, 3), "Bank", "asset", 5.0, 0.0),
    ]
    query = _Query(rows)

    with pytest.raises(HTTPException) as exc:
        dashboard._load_entries(
            _DB(query),
            date(2026, 11, 1),
            date(2026, 11, 30),
            uuid4(),
        )

    assert query.limit_value == 3
    assert exc.value.status_code == 413
    assert "2 ledger lines" in exc.value.detail


def test_load_entries_accepts_exact_database_result_limit(monkeypatch):
    monkeypatch.setattr(dashboard, "MAX_DASHBOARD_ENTRIES", 2)
    rows = [
        (date(2026, 11, 1), "Cash", "asset", 10.0, 0.0),
        (date(2026, 11, 2), "Capital", "equity", 0.0, 10.0),
    ]
    query = _Query(rows)

    result = dashboard._load_entries(
        _DB(query),
        date(2026, 11, 1),
        date(2026, 11, 30),
        uuid4(),
    )

    assert query.limit_value == 3
    assert len(result) == 2
