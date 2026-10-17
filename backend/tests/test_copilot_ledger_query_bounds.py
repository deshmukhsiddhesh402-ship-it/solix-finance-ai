from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers import copilot


def _mock_db(rows):
    db = MagicMock()
    query = db.query.return_value
    query.join.return_value = query
    query.filter.return_value = query
    query.limit.return_value = query
    query.all.return_value = rows
    return db, query


def _row(index=0):
    return (date(2026, 10, 1), f"Account {index}", "expense", 12.5, 0.0)


def test_copilot_ledger_query_is_bounded_and_keeps_complete_small_result():
    rows = [_row(1), _row(2)]
    db, query = _mock_db(rows)

    result = copilot._load_entries_for_copilot(db, "org-id")

    query.limit.assert_called_once_with(copilot.MAX_COPILOT_LEDGER_LINES + 1)
    assert result == [
        {"date": date(2026, 10, 1), "account_name": "Account 1", "account_type": "expense", "debit": 12.5, "credit": 0.0},
        {"date": date(2026, 10, 1), "account_name": "Account 2", "account_type": "expense", "debit": 12.5, "credit": 0.0},
    ]


def test_copilot_ledger_query_rejects_oversized_history_without_truncation():
    rows = [_row(index) for index in range(copilot.MAX_COPILOT_LEDGER_LINES + 1)]
    db, query = _mock_db(rows)

    with pytest.raises(HTTPException) as exc:
        copilot._load_entries_for_copilot(db, "org-id")

    assert exc.value.status_code == 413
    assert "too large" in exc.value.detail
    query.limit.assert_called_once_with(copilot.MAX_COPILOT_LEDGER_LINES + 1)
