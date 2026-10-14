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
    """Match only unambiguous one-to-one amount/type/date candidates.

    If several transactions are plausible matches, return them for review
    rather than selecting one based on input ordering.
    """
    active_bank = set(range(len(bank_lines)))
    active_book = set(range(len(book_lines)))
    matched = []

    def candidates_for(bank_index: int, book_indices: set[int]) -> list[int]:
        bank = bank_lines[bank_index]
        candidates = [
            book_index for book_index in sorted(book_indices)
            if book_lines[book_index].txn_type == bank.txn_type
            and abs(book_lines[book_index].amount - bank.amount) < 0.01
            and abs((book_lines[book_index].txn_date - bank.txn_date).days) <= date_window_days
        ]
        if not candidates:
            return []
        # Preserve the engine's closest-date preference, but retain ties so
        # equally plausible matches are sent for manual review.
        closest_days = min(
            abs((book_lines[index].txn_date - bank.txn_date).days)
            for index in candidates
        )
        return [
            index for index in candidates
            if abs((book_lines[index].txn_date - bank.txn_date).days) == closest_days
        ]

    # Repeatedly resolve pairs that are each other's sole candidate. Recompute
    # after each batch because removing confirmed pairs can disambiguate others.
    while True:
        bank_options = {
            bank_index: candidates_for(bank_index, active_book)
            for bank_index in sorted(active_bank)
        }
        book_options = {
            book_index: [
                bank_index for bank_index in active_bank
                if book_index in bank_options[bank_index]
            ]
            for book_index in sorted(active_book)
        }
        certain_pairs = [
            (bank_index, options[0])
            for bank_index, options in bank_options.items()
            if len(options) == 1 and len(book_options[options[0]]) == 1
        ]
        if not certain_pairs:
            break
        for bank_index, book_index in certain_pairs:
            if bank_index not in active_bank or book_index not in active_book:
                continue
            bank = bank_lines[bank_index]
            book = book_lines[book_index]
            matched.append({
                "bank_id": bank.id, "book_id": book.id, "amount": bank.amount,
                "txn_type": bank.txn_type, "bank_date": bank.txn_date.isoformat(),
                "book_date": book.txn_date.isoformat(),
            })
            active_bank.remove(bank_index)
            active_book.remove(book_index)

    # Any remaining candidate edges are ambiguous; keep those transactions out
    # of the ordinary unmatched classifications so they are not mislabeled as
    # bank-only items, outstanding cheques, or deposits not yet credited.
    ambiguous_bank_options = {
        bank_index: candidates_for(bank_index, active_book)
        for bank_index in sorted(active_bank)
    }
    ambiguous_bank_options = {
        bank_index: options for bank_index, options in ambiguous_bank_options.items()
        if options
    }
    ambiguous_book_indices = {
        book_index
        for options in ambiguous_bank_options.values()
        for book_index in options
    }
    ambiguous_matches = [
        {
            "bank_id": bank_lines[bank_index].id,
            "book_candidate_ids": [book_lines[index].id for index in options],
            "bank_date": bank_lines[bank_index].txn_date.isoformat(),
            "amount": bank_lines[bank_index].amount,
            "txn_type": bank_lines[bank_index].txn_type,
            "reason": "Multiple plausible transactions remain; review manually.",
        }
        for bank_index, options in ambiguous_bank_options.items()
    ]

    unmatched_bank = [
        bank_lines[index] for index in active_bank
        if index not in ambiguous_bank_options
    ]
    unmatched_book = [
        book_lines[index] for index in active_book
        if index not in ambiguous_book_indices
    ]
    outstanding_cheques = [b for b in unmatched_book if b.txn_type == "debit"]
    deposits_not_credited = [b for b in unmatched_book if b.txn_type == "credit"]
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
