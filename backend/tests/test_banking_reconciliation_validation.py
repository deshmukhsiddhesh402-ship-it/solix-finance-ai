from datetime import date

import pytest

from app.services.banking_engine import BankLine, BookLine, reconcile


def test_reconcile_rejects_negative_date_window():
    with pytest.raises(ValueError, match="date_window_days"):
        reconcile([], [], -1)


def test_reconcile_rejects_boolean_date_window():
    with pytest.raises(ValueError, match="date_window_days"):
        reconcile([], [], True)


def test_reconcile_rejects_duplicate_bank_ids():
    rows = [
        BankLine("same", date(2026, 1, 1), "receipt", 100.0, "credit"),
        BankLine("same", date(2026, 1, 2), "receipt", 100.0, "credit"),
    ]
    with pytest.raises(ValueError, match="bank transaction identifiers"):
        reconcile(rows, [])


@pytest.mark.parametrize("amount", [0.0, -1.0, float("nan"), float("inf")])
def test_reconcile_rejects_invalid_bank_amounts(amount):
    row = BankLine("bank-1", date(2026, 1, 1), "receipt", amount, "credit")
    with pytest.raises(ValueError, match="finite and greater than zero"):
        reconcile([row], [])


def test_reconcile_still_matches_valid_lines():
    bank = [BankLine("b1", date(2026, 1, 2), "UPI", 100.0, "credit")]
    books = [BookLine("l1", date(2026, 1, 1), "Receipt", 100.0, "credit")]
    result = reconcile(bank, books, date_window_days=1)
    assert result["matched_count"] == 1
