"""
Module 4: Banking — Bank Reconciliation engine.

Approach: match bank statement lines against book (cash/bank ledger) lines
using exact amount + date-window matching, since that's how reconciliation
is actually done in practice (amount is the strongest signal; narration
text matching is unreliable across banks). Anything left unmatched is
surfaced as either:
  - "Outstanding cheques / payments" (in books, not yet in bank) or
  - "Deposits not yet credited" (in books, not yet in bank) or
  - "Bank-only items" (bank charges, interest credited, etc. not yet in books)
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal


@dataclass
class BankLine:
    id: str
    txn_date: date
    description: str
    amount: float                 # always positive
    txn_type: Literal["credit", "debit"]
    mode: str = ""                # RTGS, NEFT, IMPS, UPI, CHEQUE


@dataclass
class BookLine:
    id: str
    txn_date: date
    description: str
    amount: float                 # always positive
    txn_type: Literal["credit", "debit"]  # credit = money in per books, debit = money out


def reconcile(
    bank_lines: list[BankLine],
    book_lines: list[BookLine],
    date_window_days: int = 5,
) -> dict:
    """Match bank and book lines; return matched pairs + unmatched on both sides."""
    # Track unmatched objects by identity rather than repeatedly building a
    # potentially huge candidates list. With thousands of same-day transactions,
    # the old list comprehension could allocate millions of references at once.
    unmatched_book_ids = {id(line) for line in book_lines}
    matched_bank_ids = set()
    matched = []

    for bl in bank_lines:
        # A bank credit corresponds to a book credit (money received);
        # a bank debit corresponds to a book debit (money paid out).
        best = None
        best_day_gap = None
        for bk in book_lines:
            if id(bk) not in unmatched_book_ids or bk.txn_type != bl.txn_type:
                continue
            if abs(bk.amount - bl.amount) >= 0.01:
                continue
            day_gap = abs((bk.txn_date - bl.txn_date).days)
            if day_gap > date_window_days:
                continue
            # Strictly less preserves the original first-match tie behavior.
            if best_day_gap is None or day_gap < best_day_gap:
                best = bk
                best_day_gap = day_gap

        if best is not None:
            matched.append({
                "bank_id": bl.id, "book_id": best.id, "amount": bl.amount,
                "txn_type": bl.txn_type, "bank_date": bl.txn_date.isoformat(),
                "book_date": best.txn_date.isoformat(),
            })
            matched_bank_ids.add(id(bl))
            unmatched_book_ids.remove(id(best))

    unmatched_bank = [line for line in bank_lines if id(line) not in matched_bank_ids]
    unmatched_book = [line for line in book_lines if id(line) in unmatched_book_ids]

    # Classify remaining unmatched book lines.
    outstanding_cheques = [b for b in unmatched_book if b.txn_type == "debit"]
    deposits_not_credited = [b for b in unmatched_book if b.txn_type == "credit"]
    # Remaining unmatched bank lines are bank-only items (charges, interest, etc).
    bank_only_items = list(unmatched_bank)

    total_outstanding_cheques = sum(b.amount for b in outstanding_cheques)
    total_deposits_not_credited = sum(b.amount for b in deposits_not_credited)
    total_bank_only_credits = sum(b.amount for b in bank_only_items if b.txn_type == "credit")
    total_bank_only_debits = sum(b.amount for b in bank_only_items if b.txn_type == "debit")

    return {
        "matched_count": len(matched),
        "matched": matched,
        "outstanding_cheques": [
            {"id": b.id, "date": b.txn_date.isoformat(), "description": b.description, "amount": b.amount}
            for b in outstanding_cheques
        ],
        "deposits_not_credited": [
            {"id": b.id, "date": b.txn_date.isoformat(), "description": b.description, "amount": b.amount}
            for b in deposits_not_credited
        ],
        "bank_only_items": [
            {"id": b.id, "date": b.txn_date.isoformat(), "description": b.description,
             "amount": b.amount, "txn_type": b.txn_type, "mode": b.mode}
            for b in bank_only_items
        ],
        "totals": {
            "outstanding_cheques": round(total_outstanding_cheques, 2),
            "deposits_not_credited": round(total_deposits_not_credited, 2),
            "bank_only_credits": round(total_bank_only_credits, 2),
            "bank_only_debits": round(total_bank_only_debits, 2),
        },
    }


def reconciled_balance(
    balance_as_per_bank: float,
    outstanding_cheques_total: float,
    deposits_not_credited_total: float,
) -> float:
    """Classic bank reconciliation statement formula:
    Balance as per Bank + Deposits not yet credited - Outstanding cheques = Balance as per Books
    """
    return round(balance_as_per_bank + deposits_not_credited_total - outstanding_cheques_total, 2)
