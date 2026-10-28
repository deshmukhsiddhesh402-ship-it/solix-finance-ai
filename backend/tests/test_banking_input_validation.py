"""Input validation tests for bounded bank reconciliation requests."""
import math

import pytest
from pydantic import ValidationError

from app.routers.banking import BankLineIn, BookLineIn, ReconcileRequest


def _bank_line(**overrides):
    data = {
        "id": "bank-1",
        "txn_date": "2026-10-28",
        "description": "Customer receipt",
        "amount": 1250.0,
        "txn_type": "credit",
        "mode": "NEFT",
    }
    data.update(overrides)
    return data


def _book_line(**overrides):
    data = {
        "id": "book-1",
        "txn_date": "2026-10-28",
        "description": "Customer receipt",
        "amount": 1250.0,
        "txn_type": "credit",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf"), -float("inf")])
def test_bank_line_rejects_negative_or_non_finite_amounts(amount):
    with pytest.raises(ValidationError):
        BankLineIn(**_bank_line(amount=amount))


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf"), -float("inf")])
def test_book_line_rejects_negative_or_non_finite_amounts(amount):
    with pytest.raises(ValidationError):
        BookLineIn(**_book_line(amount=amount))


@pytest.mark.parametrize("window", [-1, 32, 10**9])
def test_reconciliation_date_window_is_bounded(window):
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[], book_lines=[], date_window_days=window)


def test_reconciliation_accepts_empty_rows_and_boundary_window():
    request = ReconcileRequest(bank_lines=[], book_lines=[], date_window_days=31)
    assert request.date_window_days == 31
    assert request.bank_lines == []
    assert request.book_lines == []


def test_reconciliation_rejects_non_finite_opening_balance():
    for balance in (float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValidationError):
            ReconcileRequest(bank_lines=[], book_lines=[], balance_as_per_bank=balance)


def test_reconciliation_caps_bank_and_book_row_counts():
    too_many = [_bank_line(id=f"bank-{i}") for i in range(5001)]
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=too_many, book_lines=[])
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[], book_lines=[_book_line(id=f"book-{i}") for i in range(5001)])


def test_reconciliation_bounds_identifiers_and_descriptions():
    with pytest.raises(ValidationError):
        BankLineIn(**_bank_line(id="x" * 101))
    with pytest.raises(ValidationError):
        BookLineIn(**_book_line(description="x" * 501))
