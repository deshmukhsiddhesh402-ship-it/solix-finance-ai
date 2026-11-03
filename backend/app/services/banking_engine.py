"""
Module 4: Banking — Bank Reconciliation engine.

Approach: match bank statement lines against book (cash/bank ledger) lines
using exact amount + date-window matching, since that is how reconciliation
is commonly performed. Unmatched lines are surfaced for review; this engine
does not post or alter ledger entries.
"""
from dataclasses import dataclass
from datetime import date, datetime
import math
from typing import Literal


MAX_DATE_WINDOW_DAYS = 366
MAX_RECONCILIATION_LINES = 5_000
MAX_LINE_ID_LENGTH = 128
MAX_DESCRIPTION_LENGTH = 1_000


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


def _validate_reconciliation_lines(lines, label: str, *, is_bank: bool) -> None:
    if not isinstance(lines, list):
        raise ValueError(f"{label} must be a list.")
    if len(lines) > MAX_RECONCILIATION_LINES:
        raise ValueError(f"{label} cannot contain more than {MAX_RECONCILIATION_LINES} lines.")

    seen_ids: set[str] = set()
    for index, line in enumerate(lines):
        if not isinstance(line, BankLine if is_bank else BookLine):
            raise ValueError(f"{label}[{index}] has an invalid line type.")
        if not isinstance(line.id, str) or not line.id.strip() or len(line.id) > MAX_LINE_ID_LENGTH:
            raise ValueError(f"{label}[{index}] must have a non-empty ID of at most {MAX_LINE_ID_LENGTH} characters.")
        if line.id in seen_ids:
            raise ValueError(f"{label} contains duplicate line IDs.")
        seen_ids.add(line.id)
        if isinstance(line.txn_date, datetime) or not isinstance(line.txn_date, date):
            raise ValueError(f"{label}[{index}] must have a valid calendar date.")
        if not isinstance(line.description, str) or len(line.description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"{label}[{index}] has an invalid description.")
        if isinstance(line.amount, bool) or not isinstance(line.amount, (int, float)):
            raise ValueError(f"{label}[{index}] amount must be a finite positive number.")
        if not math.isfinite(line.amount) or line.amount <= 0:
            raise ValueError(f"{label}[{index}] amount must be a finite positive number.")
        if line.txn_type not in {"credit", "debit"}:
            raise ValueError(f"{label}[{index}] transaction type must be credit or debit.")
        if is_bank and (not isinstance(line.mode, str) or len(line.mode) > 30):
            raise ValueError(f"{label}[{index}] has an invalid payment mode.")


def reconcile(
    bank_lines: list[BankLine],
    book_lines: list[BookLine],
    date_window_days: int = 5,
) -> dict:
    """Match validated bank and book lines; return matched and unmatched items."""
    if isinstance(date_window_days, bool) or not isinstance(date_window_days, int):
        raise ValueError("date_window_days must be an integer.")
    if not 0 <= date_window_days <= MAX_DATE_WINDOW_DAYS:
        raise ValueError(f"date_window_days must be between 0 and {MAX_DATE_WINDOW_DAYS}.")

    _validate_reconciliation_lines(bank_lines, "bank_lines", is_bank=True)
    _validate_reconciliation_lines(book_lines, "book_lines", is_bank=False)

    unmatched_bank = list(bank_lines)
    unmatched_book = list(book_lines)
    matched = []

    for bl in list(unmatched_bank):
        # A bank credit corresponds to a book credit (money received);
        # a bank debit corresponds to a book debit (money paid out).
        candidates = [
            bk for bk in unmatched_book
            if bk.txn_type == bl.txn_type
            and abs(bk.amount - bl.amount) < 0.01
            and abs((bk.txn_date - bl.txn_date).days) <= date_window_days
        ]
        if candidates:
            # Prefer the closest date match.
            best = min(candidates, key=lambda bk: abs((bk.txn_date - bl.txn_date).days))
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
    """Classic BRS formula; a negative bank balance remains valid for overdrafts."""
    values = {
        "balance_as_per_bank": balance_as_per_bank,
        "outstanding_cheques_total": outstanding_cheques_total,
        "deposits_not_credited_total": deposits_not_credited_total,
    }
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number.")
    if outstanding_cheques_total < 0 or deposits_not_credited_total < 0:
        raise ValueError("Reconciliation adjustment totals cannot be negative.")
    return round(balance_as_per_bank + deposits_not_credited_total - outstanding_cheques_total, 2)
