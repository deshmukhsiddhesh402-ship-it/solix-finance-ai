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
from dataclasses import dataclass
from datetime import date
import math
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


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        return False


def _validate_reconciliation_inputs(
    bank_lines: list[BankLine],
    book_lines: list[BookLine],
    date_window_days: int,
) -> None:
    if type(date_window_days) is not int or not 0 <= date_window_days <= 31:
        raise ValueError("date_window_days must be an integer between 0 and 31.")

    for source_name, lines, expected_type in (
        ("bank_lines", bank_lines, BankLine),
        ("book_lines", book_lines, BookLine),
    ):
        if not isinstance(lines, list):
            raise ValueError(f"{source_name} must be a list of transaction lines.")
        seen_ids = set()
        for line in lines:
            # The engine is also callable outside the validated HTTP request
            # models. Reject malformed elements before dereferencing fields.
            if not isinstance(line, expected_type):
                raise ValueError(f"Each item in {source_name} must be a {expected_type.__name__} instance.")
            if not isinstance(line.id, str) or not line.id.strip() or len(line.id) > 128:
                raise ValueError(f"Each transaction ID in {source_name} must be a non-empty string of at most 128 characters.")
            if line.id in seen_ids:
                raise ValueError(f"Transaction IDs in {source_name} must be unique.")
            seen_ids.add(line.id)

            if type(line.txn_date) is not date:
                raise ValueError(f"Each transaction date in {source_name} must be a date.")
            if not _is_finite_number(line.amount) or line.amount <= 0:
                raise ValueError(f"Each transaction amount in {source_name} must be a positive finite number.")
            if line.txn_type not in ("credit", "debit"):
                raise ValueError(f"Each transaction type in {source_name} must be credit or debit.")
            if not isinstance(line.description, str) or len(line.description) > 2000:
                raise ValueError(f"Each description in {source_name} must be a string of at most 2000 characters.")
            if source_name == "bank_lines" and (
                not isinstance(line.mode, str) or len(line.mode) > 64
            ):
                raise ValueError("Each bank transaction mode must be a string of at most 64 characters.")


def reconcile(
    bank_lines: list[BankLine],
    book_lines: list[BookLine],
    date_window_days: int = 5,
) -> dict:
    """Match only unambiguous bank/book pairs; return uncertain candidates for review."""
    _validate_reconciliation_inputs(bank_lines, book_lines, date_window_days)
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
            candidate_info.append([])
            continue

        distances = [(abs((bk.txn_date - bl.txn_date).days), bk) for bk in candidates]
        best_distance = min(distance for distance, _ in distances)
        best_candidates = [bk for distance, bk in distances if distance == best_distance]
        candidate_info.append(best_candidates)
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
        best_candidates = candidate_info[index]
        if index in ambiguous_indices:
            candidate_ids = sorted(bk.id for bk in best_candidates)
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

    if not all(_is_finite_number(value) for value in (
        total_outstanding_cheques,
        total_deposits_not_credited,
        total_bank_only_credits,
        total_bank_only_debits,
    )):
        raise ValueError("Reconciliation totals exceed the supported numeric range.")

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
    values = (balance_as_per_bank, outstanding_cheques_total, deposits_not_credited_total)
    if not all(_is_finite_number(value) for value in values):
        raise ValueError("Reconciliation balances must be finite numbers.")
    result = balance_as_per_bank + deposits_not_credited_total - outstanding_cheques_total
    if not _is_finite_number(result):
        raise ValueError("Reconciled balance exceeds the supported numeric range.")
    return round(result, 2)
