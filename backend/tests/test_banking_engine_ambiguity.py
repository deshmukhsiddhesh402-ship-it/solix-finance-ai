"""Regression tests for conservative bank reconciliation matching."""
from datetime import date

from app.services.banking_engine import BankLine, BookLine, reconcile


def bank(identifier, day="2026-10-14", amount=100.0, txn_type="credit"):
    return BankLine(
        id=identifier,
        txn_date=date.fromisoformat(day),
        description="Bank transaction",
        amount=amount,
        txn_type=txn_type,
    )


def book(identifier, day="2026-10-14", amount=100.0, txn_type="credit"):
    return BookLine(
        id=identifier,
        txn_date=date.fromisoformat(day),
        description="Book transaction",
        amount=amount,
        txn_type=txn_type,
    )


def test_unique_candidate_is_matched():
    result = reconcile([bank("bank-1")], [book("book-1")])

    assert result["matched_count"] == 1
    assert result["matched"][0]["book_id"] == "book-1"
    assert result["ambiguous_matches"] == []


def test_equally_plausible_book_transactions_are_flagged_not_auto_matched():
    result = reconcile(
        [bank("bank-1")],
        [book("book-1"), book("book-2")],
    )

    assert result["matched_count"] == 0
    assert result["ambiguous_matches"] == [{
        "bank_id": "bank-1",
        "book_candidate_ids": ["book-1", "book-2"],
        "bank_date": "2026-10-14",
        "amount": 100.0,
        "txn_type": "credit",
        "reason": "Multiple plausible transactions remain; review manually.",
    }]
    assert result["bank_only_items"] == []
    assert result["deposits_not_credited"] == []


def test_multiple_bank_candidates_for_one_book_are_flagged_not_auto_matched():
    result = reconcile(
        [bank("bank-1"), bank("bank-2")],
        [book("book-1")],
    )

    assert result["matched_count"] == 0
    assert {item["bank_id"] for item in result["ambiguous_matches"]} == {"bank-1", "bank-2"}
    assert result["bank_only_items"] == []
    assert result["deposits_not_credited"] == []


def test_distinct_amounts_remain_separately_reconcilable():
    result = reconcile(
        [bank("bank-1", amount=100), bank("bank-2", amount=200)],
        [book("book-1", amount=100), book("book-2", amount=200)],
    )

    assert result["matched_count"] == 2
    assert result["ambiguous_matches"] == []
