"""Regression tests for bank-reconciliation input boundaries."""
from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.services.banking_engine import BankLine, BookLine, reconcile, reconciled_balance
from app.routers.banking import ReconcileRequest


def _bank(**overrides):
    values = {
        "id": "bank-1",
        "txn_date": date(2026, 11, 1),
        "description": "UPI receipt",
        "amount": 1180.0,
        "txn_type": "credit",
        "mode": "UPI",
    }
    return BankLine(**{**values, **overrides})


def _book(**overrides):
    values = {
        "id": "book-1",
        "txn_date": date(2026, 11, 2),
        "description": "Customer receipt",
        "amount": 1180.0,
        "txn_type": "credit",
    }
    return BookLine(**{**values, **overrides})


def test_reconcile_preserves_valid_amount_and_date_matching():
    result = reconcile([_bank()], [_book()], date_window_days=1)

    assert result["matched_count"] == 1
    assert result["matched"][0]["bank_id"] == "bank-1"
    assert result["matched"][0]["book_id"] == "book-1"


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_reconcile_rejects_invalid_bank_amounts(amount):
    with pytest.raises(ValueError, match="finite positive"):
        reconcile([_bank(amount=amount)], [])


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf")])
def test_reconcile_rejects_invalid_book_amounts(amount):
    with pytest.raises(ValueError, match="finite positive"):
        reconcile([], [_book(amount=amount)])


@pytest.mark.parametrize("window", [-1, 367, True, 1.5])
def test_reconcile_rejects_invalid_date_windows(window):
    with pytest.raises(ValueError, match="date_window_days"):
        reconcile([], [], date_window_days=window)


def test_reconcile_rejects_duplicate_ids_within_each_source():
    with pytest.raises(ValueError, match="duplicate line IDs"):
        reconcile([_bank(), _bank(txn_date=date(2026, 11, 3))], [])
    with pytest.raises(ValueError, match="duplicate line IDs"):
        reconcile([], [_book(), _book(txn_date=date(2026, 11, 3))])


def test_reconcile_rejects_invalid_date_and_transaction_type():
    with pytest.raises(ValueError, match="calendar date"):
        reconcile([_bank(txn_date=datetime(2026, 11, 1))], [])
    with pytest.raises(ValueError, match="transaction type"):
        reconcile([_bank(txn_type="transfer")], [])


def test_reconcile_rejects_oversized_line_collections():
    with pytest.raises(ValueError, match="cannot contain more than"):
        reconcile([_bank(id=f"bank-{i}") for i in range(5001)], [])


def test_reconciled_balance_allows_overdraft_but_rejects_invalid_adjustments():
    assert reconciled_balance(-500.0, 100.0, 250.0) == -350.0
    with pytest.raises(ValueError, match="adjustment totals cannot be negative"):
        reconciled_balance(100.0, -1.0, 0.0)
    with pytest.raises(ValueError, match="finite number"):
        reconciled_balance(float("nan"), 0.0, 0.0)


def test_api_schema_rejects_non_positive_and_non_finite_amounts():
    bank_line = {
        "id": "bank-1",
        "txn_date": "2026-11-01",
        "description": "UPI",
        "amount": 0,
        "txn_type": "debit",
    }
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[bank_line], book_lines=[])
    with pytest.raises(ValidationError):
        ReconcileRequest(
            bank_lines=[{**bank_line, "amount": float("nan")}],
            book_lines=[],
        )


def test_api_schema_bounds_window_and_keeps_negative_overdraft_balance():
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[], book_lines=[], date_window_days=-1)
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[], book_lines=[], date_window_days=367)

    req = ReconcileRequest(bank_lines=[], book_lines=[], balance_as_per_bank=-250.0)
    assert req.balance_as_per_bank == -250.0


def test_reconcile_rejects_aggregate_amount_overflow():
    lines = [
        _book(id="book-a", amount=1e308),
        _book(id="book-b", amount=1e308),
    ]
    with pytest.raises(ValueError, match="supported numeric range"):
        reconcile([], lines)


def test_reconciled_balance_rejects_arithmetic_overflow():
    with pytest.raises(ValueError, match="supported numeric range"):
        reconciled_balance(1e308, 0.0, 1e308)


def test_reconcile_rejects_whitespace_padded_line_ids():
    with pytest.raises(ValueError, match="trimmed"):
        reconcile([_bank(id=" bank-1 ")], [])
