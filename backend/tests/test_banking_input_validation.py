"""Regression tests for bank reconciliation request validation."""
import pytest
from pydantic import ValidationError

from app.routers.banking import BankLineIn, BookLineIn, ReconcileRequest


def bank_line(amount=100.0):
    return {
        "id": "bank-1",
        "txn_date": "2026-10-14",
        "description": "Customer payment",
        "amount": amount,
        "txn_type": "credit",
    }


def book_line(amount=100.0):
    return {
        "id": "book-1",
        "txn_date": "2026-10-14",
        "description": "Customer payment",
        "amount": amount,
        "txn_type": "credit",
    }


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_bank_line_rejects_non_positive_or_non_finite_amounts(amount):
    with pytest.raises(ValidationError):
        BankLineIn(**bank_line(amount))


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_book_line_rejects_non_positive_or_non_finite_amounts(amount):
    with pytest.raises(ValidationError):
        BookLineIn(**book_line(amount))


@pytest.mark.parametrize("days", [-1, 32])
def test_reconciliation_date_window_is_bounded(days):
    with pytest.raises(ValidationError):
        ReconcileRequest(bank_lines=[], book_lines=[], date_window_days=days)


@pytest.mark.parametrize("balance", [float("nan"), float("inf"), float("-inf")])
def test_reconciliation_rejects_non_finite_bank_balance(balance):
    with pytest.raises(ValidationError):
        ReconcileRequest(
            bank_lines=[],
            book_lines=[],
            balance_as_per_bank=balance,
        )


def test_reconciliation_allows_negative_bank_balance_for_overdraft():
    request = ReconcileRequest(
        bank_lines=[],
        book_lines=[],
        balance_as_per_bank=-250.0,
    )
    assert request.balance_as_per_bank == -250.0
