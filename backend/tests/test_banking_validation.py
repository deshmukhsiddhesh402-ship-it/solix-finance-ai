"""Input validation regression tests for bank reconciliation requests."""
from datetime import date

import pytest
from pydantic import ValidationError

from app.routers.banking import BankLineIn, BookLineIn, ReconcileRequest


def test_bank_line_rejects_non_finite_or_negative_amount():
    base = {
        "id": "bank-1",
        "txn_date": date(2026, 10, 1),
        "description": "Receipt",
        "txn_type": "credit",
    }
    for amount in (float("nan"), float("inf"), float("-inf"), -1):
        with pytest.raises(ValidationError):
            BankLineIn(**base, amount=amount)


def test_book_line_rejects_non_finite_or_negative_amount():
    base = {
        "id": "book-1",
        "txn_date": date(2026, 10, 1),
        "description": "Receipt",
        "txn_type": "credit",
    }
    for amount in (float("nan"), float("inf"), float("-inf"), -1):
        with pytest.raises(ValidationError):
            BookLineIn(**base, amount=amount)


@pytest.mark.parametrize("days", [-1, 366, 1.5])
def test_reconciliation_rejects_invalid_date_window(days):
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[], book_lines=[], date_window_days=days)


@pytest.mark.parametrize("balance", [float("nan"), float("inf"), float("-inf")])
def test_reconciliation_rejects_non_finite_opening_balance(balance):
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[], book_lines=[], balance_as_per_bank=balance)


def test_reconciliation_bounds_line_counts():
    line = {
        "id": "line",
        "txn_date": date(2026, 10, 1),
        "description": "Receipt",
        "amount": 1,
        "txn_type": "credit",
    }
    lines = [BankLineIn(**{**line, "id": f"bank-{i}"}) for i in range(1001)]
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=lines, book_lines=[])
