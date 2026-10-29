"""Regression tests for bank-reconciliation engine input validation."""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.banking_engine import (
    BankLine,
    BookLine,
    reconcile,
    reconciled_balance,
)


def _bank(identifier="bank-1", amount=100.0, txn_type="credit"):
    return BankLine(identifier, date(2026, 10, 1), "Customer receipt", amount, txn_type, "NEFT")


def _book(identifier="book-1", amount=100.0, txn_type="credit"):
    return BookLine(identifier, date(2026, 10, 1), "Customer receipt", amount, txn_type)


def test_valid_lines_reconcile_as_before():
    result = reconcile([_bank()], [_book()])
    assert result["matched_count"] == 1
    assert result["matched"][0]["bank_id"] == "bank-1"


@pytest.mark.parametrize("window", [-1, 32, True, 1.5])
def test_reconcile_rejects_invalid_date_windows(window):
    with pytest.raises(ValueError):
        reconcile([_bank()], [_book()], window)


@pytest.mark.parametrize("amount", [-1, float("nan"), float("inf")])
def test_reconcile_rejects_invalid_bank_amounts(amount):
    with pytest.raises(ValueError):
        reconcile([_bank(amount=amount)], [])


def test_reconcile_rejects_duplicate_ids_on_same_side():
    with pytest.raises(ValueError, match="identifiers must be unique"):
        reconcile([_bank(), _bank()], [])


def test_reconcile_rejects_unbounded_descriptions_and_invalid_modes():
    with pytest.raises(ValueError, match="descriptions"):
        reconcile([BankLine("b", date(2026, 10, 1), "x" * 1001, 1, "credit")], [])
    with pytest.raises(ValueError, match="mode"):
        reconcile([BankLine("b", date(2026, 10, 1), "x", 1, "credit", "m" * 41)], [])


@pytest.mark.parametrize(
    "args",
    [
        (100, float("nan"), 0),
        (100, -1, 0),
        (100, 0, float("inf")),
    ],
)
def test_reconciled_balance_rejects_invalid_adjustments(args):
    with pytest.raises(ValueError):
        reconciled_balance(*args)


def test_reconciled_balance_accepts_valid_values():
    assert reconciled_balance(1000, 200, 50) == 850
