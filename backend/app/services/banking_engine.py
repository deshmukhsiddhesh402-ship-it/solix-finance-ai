"""
Module 4: Banking — Bank Reconciliation engine.

Matches bank and book lines by transaction type, amount, and date window.
Unmatched lines are returned for human review; this engine never posts
or alters ledger entries.
"""
from dataclasses import dataclass
from datetime import date, datetime
import math
from typing import Literal

MAX_DATE_WINDOW_DAYS = 366
MAX_RECONCILIATION_LINES = 5_000
MAX_LINE_ID_LENGTH = 128
MAX_DESCRIPTION_LENGTH = 1_000


def _finite_number(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


@dataclass
class BankLine:
    id: str
    txn_date: date
    description: str
    amount: float
    txn_type: Literal["credit", "debit"]
    mode: str = ""


@dataclass
class BookLine:
    id: str
    txn_date: date
    description: str
    amount: float
    txn_type: Literal["credit", "debit"]


def _validate_lines(lines, label: str, expected_type, *, bank: bool = False) -> None:
    if not isinstance(lines, list):
        raise ValueError(f"{label} must be a list.")
    if len(lines) > MAX_RECONCILIATION_LINES:
        raise ValueError(f"{label} cannot contain more than {MAX_RECONCILIATION_LINES} lines.")

    seen_ids: set[str] = set()
    for index, line in enumerate(lines):
        if not isinstance(line, expected_type):
            raise ValueError(f"{label}[{index}] has an invalid line type.")
        if (not isinstance(line.id, str) or not line.id.strip()
                or line.id != line.id.strip() or len(line.id) > MAX_LINE_ID_LENGTH):
            raise ValueError(f"{label}[{index}] must have a trimmed, non-empty ID of at most {MAX_LINE_ID_LENGTH} characters.")
        if line.id in seen_ids:
            raise ValueError(f"{label} contains duplicate line IDs.")
        seen_ids.add(line.id)
        if isinstance(line.txn_date, datetime) or not isinstance(line.txn_date, date):
            raise ValueError(f"{label}[{index}] must have a valid calendar date.")
        if not isinstance(line.description, str) or len(line.description) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"{label}[{index}] has an invalid description.")
        if not _finite_number(line.amount) or line.amount <= 0:
            raise ValueError(f"{label}[{index}] amount must be a finite positive number.")
        if line.txn_type not in {"credit", "debit"}:
            raise ValueError(f"{label}[{index}] transaction type must be credit or debit.")
        if bank and (not isinstance(line.mode, str) or len(line.mode) > 30):
            raise ValueError(f"{label}[{index}] has an invalid payment mode.")


def _safe_total(lines, label: str) -> float:
    try:
        total = math.fsum(line.amount for line in lines)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label} total exceeds the supported numeric range.") from exc
    if not math.isfinite(total):
        raise ValueError(f"{label} total exceeds the supported numeric range.")
    return total


def reconcile(
    bank_lines: list[BankLine],
    book_lines: list[BookLine],
    date_window_days: int = 5,
) -> dict:
    """Validate and match bank and book lines; return matched and unmatched items."""
    if isinstance(date_window_days, bool) or not isinstance(date_window_days, int):
        raise ValueError("date_window_days must be an integer.")
    if not 0 <= date_window_days <= MAX_DATE_WINDOW_DAYS:
        raise ValueError(f"date_window_days must be between 0 and {MAX_DATE_WINDOW_DAYS}.")

    _validate_lines(bank_lines, "bank_lines", BankLine, bank=True)
    _validate_lines(book_lines, "book_lines", BookLine)

    unmatched_bank = list(bank_lines)
    unmatched_book = list(book_lines)
    matched = []

    for bank_line in list(unmatched_bank):
        candidates = [
            book_line for book_line in unmatched_book
            if book_line.txn_type == bank_line.txn_type
            and abs(book_line.amount - bank_line.amount) < 0.01
            and abs((book_line.txn_date - bank_line.txn_date).days) <= date_window_days
        ]
        if candidates:
            best = min(candidates, key=lambda line: abs((line.txn_date - bank_line.txn_date).days))
            matched.append({
                "bank_id": bank_line.id,
                "book_id": best.id,
                "amount": bank_line.amount,
                "txn_type": bank_line.txn_type,
                "bank_date": bank_line.txn_date.isoformat(),
                "book_date": best.txn_date.isoformat(),
            })
            unmatched_bank.remove(bank_line)
            unmatched_book.remove(best)

    outstanding_cheques = [line for line in unmatched_book if line.txn_type == "debit"]
    deposits_not_credited = [line for line in unmatched_book if line.txn_type == "credit"]
    bank_only_items = list(unmatched_bank)

    total_outstanding = _safe_total(outstanding_cheques, "Outstanding cheque")
    total_deposits = _safe_total(deposits_not_credited, "Deposit")
    total_bank_credits = _safe_total([line for line in bank_only_items if line.txn_type == "credit"], "Bank-only credit")
    total_bank_debits = _safe_total([line for line in bank_only_items if line.txn_type == "debit"], "Bank-only debit")

    return {
        "matched_count": len(matched),
        "matched": matched,
        "outstanding_cheques": [
            {"id": line.id, "date": line.txn_date.isoformat(), "description": line.description, "amount": line.amount}
            for line in outstanding_cheques
        ],
        "deposits_not_credited": [
            {"id": line.id, "date": line.txn_date.isoformat(), "description": line.description, "amount": line.amount}
            for line in deposits_not_credited
        ],
        "bank_only_items": [
            {"id": line.id, "date": line.txn_date.isoformat(), "description": line.description,
             "amount": line.amount, "txn_type": line.txn_type, "mode": line.mode}
            for line in bank_only_items
        ],
        "totals": {
            "outstanding_cheques": round(total_outstanding, 2),
            "deposits_not_credited": round(total_deposits, 2),
            "bank_only_credits": round(total_bank_credits, 2),
            "bank_only_debits": round(total_bank_debits, 2),
        },
    }


def reconciled_balance(
    balance_as_per_bank: float,
    outstanding_cheques_total: float,
    deposits_not_credited_total: float,
) -> float:
    """BRS formula: bank balance + deposits not credited - outstanding cheques."""
    values = (balance_as_per_bank, outstanding_cheques_total, deposits_not_credited_total)
    if not all(_finite_number(value) for value in values):
        raise ValueError("Reconciliation balances must be finite numbers.")
    if outstanding_cheques_total < 0 or deposits_not_credited_total < 0:
        raise ValueError("Reconciliation adjustment totals cannot be negative.")
    result = balance_as_per_bank + deposits_not_credited_total - outstanding_cheques_total
    if not math.isfinite(result):
        raise ValueError("Reconciled balance exceeds the supported numeric range.")
    return round(result, 2)
