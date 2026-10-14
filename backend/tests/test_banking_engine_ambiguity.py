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


def test_closest_date_candidate_is_preferred_when_not_tied():
    result = reconcile(
        [bank("bank-1", day="2026-10-14")],
        [
            book("book-near", day="2026-10-13"),
            book("book-far", day="2026-10-11"),
        ],
        date_window_days=5,
    )

    assert result["matched_count"] == 1
    assert result["matched"][0]["book_id"] == "book-near"
    assert result["ambiguous_matches"] == []
    assert [item["id"] for item in result["deposits_not_credited"]] == ["book-far"]


def test_opposite_transaction_types_are_not_matched():
    result = reconcile(
        [bank("bank-credit", txn_type="credit")],
        [book("book-debit", txn_type="debit")],
    )

    assert result["matched_count"] == 0
    assert result["ambiguous_matches"] == []
    assert [item["id"] for item in result["bank_only_items"]] == ["bank-credit"]
    assert [item["id"] for item in result["outstanding_cheques"]] == ["book-debit"]


def test_transaction_outside_date_window_is_not_matched():
    result = reconcile(
        [bank("bank-1", day="2026-10-14")],
        [book("book-1", day="2026-10-01")],
        date_window_days=5,
    )

    assert result["matched_count"] == 0
    assert result["ambiguous_matches"] == []
    assert [item["id"] for item in result["bank_only_items"]] == ["bank-1"]
    assert [item["id"] for item in result["deposits_not_credited"]] == ["book-1"]



def test_ambiguous_reconciliation_withholds_final_book_balance():
    from app.routers.banking import ReconcileRequest, reconcile_endpoint

    request = ReconcileRequest(
        bank_lines=[{
            "id": "bank-1", "txn_date": "2026-10-14", "description": "Payment",
            "amount": 100, "txn_type": "credit",
        }],
        book_lines=[
            {"id": "book-1", "txn_date": "2026-10-14", "description": "Payment A", "amount": 100, "txn_type": "credit"},
            {"id": "book-2", "txn_date": "2026-10-14", "description": "Payment B", "amount": 100, "txn_type": "credit"},
        ],
        balance_as_per_bank=1000,
    )

    result = reconcile_endpoint(request, org_id="00000000-0000-0000-0000-000000000001", _user="test-user")

    statement = result["reconciliation_statement"]
    assert statement["manual_review_required"] is True
    assert statement["ambiguous_transaction_count"] == 1
    assert statement["balance_as_per_books"] is None
