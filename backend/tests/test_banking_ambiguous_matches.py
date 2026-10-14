"""Regression tests for ambiguous bank reconciliation matches."""
from datetime import date

from app.services.banking_engine import BankLine, BookLine, reconcile


def bank(identifier="bank-1", day=14, amount=100.0, txn_type="credit"):
    return BankLine(identifier, date(2026, 10, day), "Payment", amount, txn_type)


def book(identifier, day, amount=100.0, txn_type="credit"):
    return BookLine(identifier, date(2026, 10, day), "Payment", amount, txn_type)


def test_equal_closest_candidates_are_flagged_and_not_auto_matched():
    result = reconcile(
        [bank(day=14)],
        [book("book-before", 13), book("book-after", 15)],
        date_window_days=5,
    )

    assert result["matched_count"] == 0
    assert result["matched"] == []
    assert result["ambiguous_matches"] == [{
        "bank_id": "bank-1",
        "candidate_book_ids": ["book-before", "book-after"],
        "reason": "Multiple book transactions have the same amount, type, and closest date; manual review required.",
    }]
    assert {row["id"] for row in result["deposits_not_credited"]} == {"book-before", "book-after"}
    assert [row["id"] for row in result["bank_only_items"]] == ["bank-1"]


def test_unique_closest_candidate_is_still_matched():
    result = reconcile(
        [bank(day=14)],
        [book("closest", 14), book("farther", 16)],
        date_window_days=5,
    )

    assert result["matched_count"] == 1
    assert result["matched"][0]["book_id"] == "closest"
    assert result["ambiguous_matches"] == []


def test_different_transaction_types_are_not_ambiguous_candidates():
    result = reconcile(
        [bank(day=14, txn_type="credit")],
        [book("debit", 14, txn_type="debit"), book("credit", 14)],
        date_window_days=5,
    )

    assert result["matched_count"] == 1
    assert result["matched"][0]["book_id"] == "credit"
    assert result["ambiguous_matches"] == []


def test_two_bank_lines_competing_for_one_book_line_are_both_flagged():
    result = reconcile(
        [bank("bank-a", day=14), bank("bank-b", day=14)],
        [book("book-only", 14)],
        date_window_days=5,
    )

    assert result["matched_count"] == 0
    assert result["matched"] == []
    assert result["ambiguous_matches"] == [
        {
            "bank_id": "bank-a",
            "candidate_book_ids": ["book-only"],
            "reason": "Multiple bank transactions compete for the same closest book transaction; manual review required.",
        },
        {
            "bank_id": "bank-b",
            "candidate_book_ids": ["book-only"],
            "reason": "Multiple bank transactions compete for the same closest book transaction; manual review required.",
        },
    ]
    assert [row["id"] for row in result["bank_only_items"]] == ["bank-a", "bank-b"]
    assert [row["id"] for row in result["deposits_not_credited"]] == ["book-only"]


def test_cross_side_conflict_is_not_resolved_by_input_order():
    book_line = book("book-only", 14)
    forward = reconcile(
        [bank("bank-a", day=14), bank("bank-b", day=14)],
        [book_line],
        date_window_days=5,
    )
    reverse = reconcile(
        [bank("bank-b", day=14), bank("bank-a", day=14)],
        [book_line],
        date_window_days=5,
    )

    assert forward["matched"] == reverse["matched"] == []
    assert {
        item["bank_id"] for item in forward["ambiguous_matches"]
    } == {
        item["bank_id"] for item in reverse["ambiguous_matches"]
    } == {"bank-a", "bank-b"}


def test_tied_candidate_ids_are_stable_when_book_input_order_changes():
    bank_line = bank(day=14)
    before = book("book-before", 13)
    after = book("book-after", 15)

    forward = reconcile([bank_line], [before, after], date_window_days=5)
    reverse = reconcile([bank_line], [after, before], date_window_days=5)

    assert forward["matched"] == reverse["matched"] == []
    assert forward["ambiguous_matches"] == reverse["ambiguous_matches"]
    assert forward["ambiguous_matches"][0]["candidate_book_ids"] == [
        "book-after",
        "book-before",
    ]
