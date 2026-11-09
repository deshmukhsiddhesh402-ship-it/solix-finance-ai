"""Regression tests for boolean values in Decimal simulator API fields."""
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.accounting_simulator import CashBookRequest, CashTransactionInput, JournalLineInput


@pytest.mark.parametrize("field", ["debit", "credit"])
@pytest.mark.parametrize("value", [True, False])
def test_simulator_journal_lines_reject_boolean_decimal_amounts(field, value):
    payload = {"account": "Cash", "debit": "10.00", "credit": "0.00"}
    payload[field] = value

    with pytest.raises(ValidationError, match="decimal amount, not a boolean"):
        JournalLineInput(**payload)


@pytest.mark.parametrize("value", [True, False])
def test_simulator_cash_transactions_reject_boolean_decimal_amount(value):
    with pytest.raises(ValidationError, match="decimal amount, not a boolean"):
        CashTransactionInput(description="Cash sale", amount=value)


@pytest.mark.parametrize("value", [True, False])
def test_simulator_cash_book_rejects_boolean_opening_balance(value):
    with pytest.raises(ValidationError, match="decimal amount, not a boolean"):
        CashBookRequest(opening_balance=value)


def test_simulator_decimal_requests_continue_accepting_string_amounts():
    line = JournalLineInput(account="Cash", debit="10.00", credit="0.00")
    transaction = CashTransactionInput(description="Cash sale", amount="10.00")
    cash_book = CashBookRequest(opening_balance="100.00", receipts=[transaction])

    assert str(line.debit) == "10.00"
    assert str(transaction.amount) == "10.00"
    assert str(cash_book.opening_balance) == "100.00"
