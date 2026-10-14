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
    """Match only unambiguous bank/book pairs; return uncertain candidates for review."""
    unmatched_bank = list(bank_lines)
    unmatched_book = list(book_lines)
    matched = []
    ambiguous_matches = []

    # Resolve each bank line's nearest candidate against the original book
    # population first. A greedy one-pass loop can otherwise consume a book
    # line for the first bank line even when another bank line has an equally
    # plausible claim to it.
    candidate_info = []
    best_claims = {}
    ambiguous_indices = set()
    for index, bl in enumerate(bank_lines):
        candidates = [
            bk for bk in book_lines
            if bk.txn_type == bl.txn_type
            and abs(bk.amount - bl.amount) < 0.01
            and abs((bk.txn_date - bl.txn_date).days) <= date_window_days
        ]
        if not candidates:
            candidate_info.append(([], []))
            continue

        distances = [(abs((bk.txn_date - bl.txn_date).days), bk) for bk in candidates]
        best_distance = min(distance for distance, _ in distances)
        best_candidates = [bk for distance, bk in distances if distance == best_distance]
        candidate_info.append((candidates, best_candidates))
        if len(best_candidates) > 1:
            ambiguous_indices.add(index)
        for bk in best_candidates:
            best_claims.setdefault(id(bk), []).append(index)

    # If multiple bank lines claim the same closest book line, flag every
    # claimant. Do not let input ordering silently decide which bank line wins.
    cross_side_conflicts = {
        index
        for claimants in best_claims.values() if len(claimants) > 1
        for index in claimants
    }
    ambiguous_indices.update(cross_side_conflicts)

    for index, bl in enumerate(bank_lines):
        candidates, best_candidates = candidate_info[index]
        if index in ambiguous_indices:
            candidate_ids = [bk.id for bk in best_candidates]
            if len(best_candidates) > 1:
                reason = "Multiple book transactions have the same amount, type, and closest date; manual review required."
            else:
                reason = "Multiple bank transactions compete for the same closest book transaction; manual review required."
            ambiguous_matches.append({
                "bank_id": bl.id,
                "candidate_book_ids": candidate_ids,
                "reason": reason,
            })
            continue
        if not best_candidates:
            continue

        best = best_candidates[0]
        # A candidate shared by multiple best-match claims was marked ambiguous
        # above, so this removal is independent of input ordering.
        matched.append({
            "bank_id": bl.id, "book_id": best.id, "amount": bl.amount,
            "txn_type": bl.txn_type, "bank_date": bl.txn_date.isoformat(),
            "book_date": best.txn_date.isoformat(),
        })
        unmatched_bank.remove(bl)
        unmatched_book.remove(best)

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
        "ambiguous_matches": ambiguous_matches,
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
