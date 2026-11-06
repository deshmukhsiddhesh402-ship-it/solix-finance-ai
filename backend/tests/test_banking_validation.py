"""Regression coverage for bank-reconciliation validation and HTTP errors."""
from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.banking import ReconcileRequest, reconcile_endpoint
from app.services.banking_engine import BankLine, BookLine, reconcile, reconciled_balance


def bank_line(**overrides):
    values = {
        "id": "bank-1", "txn_date": date(2026, 11, 1),
        "description": "UPI receipt", "amount": 1180.0,
        "txn_type": "credit", "mode": "UPI",
    }
    return BankLine(**{**values, **overrides})


def book_line(**overrides):
    values = {
        "id": "book-1", "txn_date": date(2026, 11, 2),
        "description": "Customer receipt", "amount": 1180.0,
        "txn_type": "credit",
    }
    return BookLine(**{**values, **overrides})


def test_valid_lines_still_match():
    result = reconcile([bank_line()], [book_line()], date_window_days=1)
    assert result["matched_count"] == 1
    assert result["matched"][0]["bank_id"] == "bank-1"


@pytest.mark.parametrize("amount", [0, -1, float("nan"), float("inf"), float("-inf")])
def test_invalid_amounts_are_rejected(amount):
    with pytest.raises(ValueError, match="finite positive"):
        reconcile([bank_line(amount=amount)], [])


def test_duplicate_ids_are_rejected_per_source():
    with pytest.raises(ValueError, match="duplicate line IDs"):
        reconcile([bank_line(), bank_line(txn_date=date(2026, 11, 3))], [])
    with pytest.raises(ValueError, match="duplicate line IDs"):
        reconcile([], [book_line(), book_line(txn_date=date(2026, 11, 3))])


@pytest.mark.parametrize("window", [-1, 367, True, 1.5])
def test_invalid_date_windows_are_rejected(window):
    with pytest.raises(ValueError, match="date_window_days"):
        reconcile([], [], date_window_days=window)


def test_line_count_and_id_bounds_are_enforced():
    with pytest.raises(ValueError, match="more than"):
        reconcile([bank_line(id=f"bank-{index}") for index in range(5001)], [])
    with pytest.raises(ValueError, match="trimmed"):
        reconcile([bank_line(id=" bank-1 ")], [])


def test_aggregate_overflow_is_rejected():
    lines = [book_line(id="book-a", amount=1e308), book_line(id="book-b", amount=1e308)]
    with pytest.raises(ValueError, match="supported numeric range"):
        reconcile([], lines)


def test_overdraft_balance_is_valid_but_non_finite_balance_is_not():
    assert reconciled_balance(-500.0, 100.0, 250.0) == -350.0
    with pytest.raises(ValueError, match="finite numbers"):
        reconciled_balance(float("nan"), 0.0, 0.0)


def test_api_schema_rejects_non_positive_and_non_finite_amounts():
    payload = {
        "bank_lines": [{
            "id": "bank-1", "txn_date": "2026-11-01",
            "description": "UPI", "amount": 0, "txn_type": "debit",
        }],
        "book_lines": [],
    }
    with pytest.raises(ValidationError):
        ReconcileRequest(**payload)
    payload["bank_lines"][0]["amount"] = float("nan")
    with pytest.raises(ValidationError):
        ReconcileRequest(**payload)


def test_endpoint_maps_expected_service_validation_to_http_422():
    request = ReconcileRequest(
        bank_lines=[
            {"id": "duplicate", "txn_date": "2026-11-01", "description": "A", "amount": 10, "txn_type": "credit"},
            {"id": "duplicate", "txn_date": "2026-11-02", "description": "B", "amount": 20, "txn_type": "credit"},
        ],
        book_lines=[],
    )
    with pytest.raises(HTTPException) as exc:
        reconcile_endpoint(request, org_id="org-test", _user="test-user")
    assert exc.value.status_code == 422
    assert "duplicate line IDs" in exc.value.detail
