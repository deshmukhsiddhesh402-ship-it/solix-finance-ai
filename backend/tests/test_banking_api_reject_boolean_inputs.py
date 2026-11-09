"""Request-boundary regression tests for boolean reconciliation amounts."""
from datetime import date
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.banking import BankLineIn, BookLineIn, ReconcileRequest


@pytest.mark.parametrize("model", [BankLineIn, BookLineIn])
@pytest.mark.parametrize("value", [True, False])
def test_bank_and_book_line_requests_reject_boolean_amounts(model, value):
    payload = {
        "id": "line-1",
        "txn_date": date(2026, 11, 1),
        "description": "Customer receipt",
        "amount": value,
        "txn_type": "credit",
    }
    if model is BankLineIn:
        payload["mode"] = "NEFT"

    with pytest.raises(ValidationError, match="numeric, not boolean"):
        model(**payload)


@pytest.mark.parametrize("field", ["date_window_days", "balance_as_per_bank"])
@pytest.mark.parametrize("value", [True, False])
def test_reconciliation_request_rejects_boolean_control_and_balance_values(field, value):
    payload = {
        "bank_lines": [],
        "book_lines": [],
        "date_window_days": 5,
        "balance_as_per_bank": 1000,
    }
    payload[field] = value

    with pytest.raises(ValidationError, match="numeric, not boolean"):
        ReconcileRequest(**payload)


def test_reconciliation_request_continues_accepting_integer_amounts():
    bank = BankLineIn(
        id="bank-1",
        txn_date=date(2026, 11, 1),
        description="Customer receipt",
        amount=100,
        txn_type="credit",
        mode="NEFT",
    )
    book = BookLineIn(
        id="book-1",
        txn_date=date(2026, 11, 1),
        description="Customer receipt",
        amount=100,
        txn_type="credit",
    )
    request = ReconcileRequest(
        bank_lines=[bank],
        book_lines=[book],
        date_window_days=5,
        balance_as_per_bank=1000,
    )

    assert request.bank_lines[0].amount == 100.0
    assert request.book_lines[0].amount == 100.0
    assert request.date_window_days == 5
    assert request.balance_as_per_bank == 1000.0
