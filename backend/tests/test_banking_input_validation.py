"""Regression tests for bank reconciliation request validation."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.banking import (
    BankLineIn,
    BookLineIn,
    ReconcileRequest,
    reconcile_endpoint,
)


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



def test_reconciliation_rejects_duplicate_bank_transaction_ids():
    duplicate = bank_line()
    duplicate["txn_date"] = "2026-10-15"
    with pytest.raises(ValidationError, match="bank_lines must be unique"):
        ReconcileRequest(bank_lines=[bank_line(), duplicate], book_lines=[])


def test_reconciliation_rejects_duplicate_book_transaction_ids():
    duplicate = book_line()
    duplicate["txn_date"] = "2026-10-15"
    with pytest.raises(ValidationError, match="book_lines must be unique"):
        ReconcileRequest(bank_lines=[], book_lines=[book_line(), duplicate])


def test_reconciliation_allows_same_id_once_in_each_source():
    bank = bank_line()
    book = book_line()
    book["id"] = bank["id"]
    request = ReconcileRequest(bank_lines=[bank], book_lines=[book])
    assert request.bank_lines[0].id == request.book_lines[0].id


def test_reconciliation_endpoint_returns_422_for_aggregate_overflow():
    request = ReconcileRequest(
        bank_lines=[],
        book_lines=[
            {**book_line(amount=1e308), "id": "book-large-1"},
            {**book_line(amount=1e308), "id": "book-large-2"},
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        reconcile_endpoint(request, org_id="test-org", _user="test-user")

    assert exc_info.value.status_code == 422
    assert "supported numeric range" in exc_info.value.detail
