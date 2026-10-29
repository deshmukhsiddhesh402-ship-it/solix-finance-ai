"""Regression tests for memory-bounded bank reconciliation matching."""
from datetime import date

from app.services.banking_engine import BankLine, BookLine, reconcile


def test_reconcile_uses_nearest_date_and_consumes_each_book_line_once():
    bank_lines = [
        BankLine("bank-1", date(2026, 10, 10), "Receipt", 100.0, "credit"),
        BankLine("bank-2", date(2026, 10, 12), "Receipt", 100.0, "credit"),
        BankLine("bank-3", date(2026, 10, 20), "Other", 50.0, "debit"),
    ]
    book_lines = [
        BookLine("book-1", date(2026, 10, 11), "Receipt", 100.0, "credit"),
        BookLine("book-2", date(2026, 10, 13), "Receipt", 100.0, "credit"),
        BookLine("book-3", date(2026, 10, 20), "Charge", 25.0, "debit"),
    ]

    result = reconcile(bank_lines, book_lines, date_window_days=2)

    assert result["matched_count"] == 2
    assert [(item["bank_id"], item["book_id"]) for item in result["matched"]] == [
        ("bank-1", "book-1"),
        ("bank-2", "book-2"),
    ]
    assert [item["id"] for item in result["outstanding_cheques"]] == ["book-3"]
    assert [item["id"] for item in result["bank_only_items"]] == ["bank-3"]


def test_reconcile_preserves_first_book_line_when_date_gaps_tie():
    bank_lines = [
        BankLine("bank-1", date(2026, 10, 10), "Receipt", 100.0, "credit"),
    ]
    book_lines = [
        BookLine("book-first", date(2026, 10, 9), "Receipt", 100.0, "credit"),
        BookLine("book-second", date(2026, 10, 11), "Receipt", 100.0, "credit"),
    ]

    result = reconcile(bank_lines, book_lines, date_window_days=2)

    assert result["matched"][0]["book_id"] == "book-first"
    assert [item["id"] for item in result["deposits_not_credited"]] == ["book-second"]
