"""Regression tests for overflow in bank reconciliation totals."""
from datetime import date

import pytest

from app.services.banking_engine import BookLine, reconcile, reconciled_balance


def test_reconcile_rejects_overflowing_unmatched_book_total():
    lines = [
        BookLine("debit-1", date(2026, 10, 29), "Payment 1", 1e308, "debit"),
        BookLine("debit-2", date(2026, 10, 29), "Payment 2", 1e308, "debit"),
    ]

    with pytest.raises(ValueError, match="outstanding cheque total must be finite"):
        reconcile([], lines)


def test_reconciled_balance_rejects_overflowing_result():
    with pytest.raises(ValueError, match="Reconciled balance must be finite"):
        reconciled_balance(1e308, 1e308, 1e308)
