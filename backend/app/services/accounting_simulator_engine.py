"""Deterministic, Decimal-based primitives for the accounting learning simulator.

This module is additive: it does not replace the existing production accounting engine.
Amounts are represented in INR with two decimal places; floats are converted through
str() to avoid importing their binary representation into Decimal arithmetic.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value: Decimal | int | float | str, label: str = "amount") -> Decimal:
    """Convert a value to a non-negative, paise-precision Decimal."""
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a monetary amount, not a boolean.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{label} must be a valid decimal amount.") from None
    if not amount.is_finite():
        raise ValueError(f"{label} must be finite.")
    if amount < 0:
        raise ValueError(f"{label} cannot be negative.")
    quantized = amount.quantize(CENT)
    if amount != quantized:
        raise ValueError(f"{label} cannot have fractions smaller than one paisa.")
    return quantized


@dataclass(frozen=True)
class JournalLine:
    account: str
    debit: Decimal | int | float | str = ZERO
    credit: Decimal | int | float | str = ZERO


@dataclass(frozen=True)
class JournalEntry:
    lines: tuple[JournalLine, ...]
    narration: str = ""


def validate_journal_entry(entry: JournalEntry) -> dict:
    """Validate a compound entry and return exact debit/credit totals.

    Educational narration requirements are intentionally not enforced here: narration
    style belongs to a learning exercise, not the general-purpose accounting engine.
    """
    if not isinstance(entry, JournalEntry):
        raise ValueError("entry must be a JournalEntry.")
    if len(entry.lines) < 2:
        raise ValueError("A journal entry must contain at least two lines.")
    debit_total = ZERO
    credit_total = ZERO
    for line in entry.lines:
        if not isinstance(line, JournalLine):
            raise ValueError("Journal lines must be JournalLine objects.")
        if not isinstance(line.account, str) or not line.account.strip():
            raise ValueError("Account name must be non-empty.")
        debit = money(line.debit, "debit")
        credit = money(line.credit, "credit")
        if debit > ZERO and credit > ZERO:
            raise ValueError("A journal line cannot contain both debit and credit.")
        if debit == ZERO and credit == ZERO:
            raise ValueError("A journal line must contain a debit or credit amount.")
        debit_total += debit
        credit_total += credit
    if debit_total != credit_total:
        raise ValueError(
            f"Journal entry is unbalanced: debits {debit_total} != credits {credit_total}."
        )
    return {
        "is_balanced": True,
        "total_debit": debit_total,
        "total_credit": credit_total,
        "line_count": len(entry.lines),
    }


def build_general_ledger(entries: Iterable[JournalEntry]) -> dict[str, dict]:
    """Aggregate validated journal lines into account debit/credit totals."""
    ledger: dict[str, dict] = {}
    for entry in entries:
        validate_journal_entry(entry)
        for line in entry.lines:
            debit = money(line.debit, "debit")
            credit = money(line.credit, "credit")
            account = ledger.setdefault(
                line.account.strip(),
                {"total_debit": ZERO, "total_credit": ZERO, "balance": ZERO,
                 "balance_side": "zero"},
            )
            account["total_debit"] += debit
            account["total_credit"] += credit
    for account in ledger.values():
        net = account["total_debit"] - account["total_credit"]
        account["balance"] = abs(net)
        account["balance_side"] = "debit" if net > ZERO else "credit" if net < ZERO else "zero"
    return ledger


def build_trial_balance(ledger: dict[str, dict]) -> dict:
    """Create net debit/credit trial-balance rows from a validated general ledger."""
    if not isinstance(ledger, dict):
        raise ValueError("ledger must be a mapping of account names to balances.")
    rows = []
    total_debit = ZERO
    total_credit = ZERO
    for account_name, account in ledger.items():
        if not isinstance(account_name, str) or not account_name.strip():
            raise ValueError("Trial balance account names must be non-empty.")
        if not isinstance(account, dict) or account.get("balance_side") not in {"debit", "credit", "zero"}:
            raise ValueError("Invalid ledger account balance.")
        balance = money(account.get("balance"), "balance")
        debit = balance if account["balance_side"] == "debit" else ZERO
        credit = balance if account["balance_side"] == "credit" else ZERO
        rows.append({"account": account_name, "debit": debit, "credit": credit})
        total_debit += debit
        total_credit += credit
    return {
        "rows": rows,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": total_debit == total_credit,
    }


def build_t_account(total_debit: Decimal | int | float | str,
                    total_credit: Decimal | int | float | str) -> dict:
    """Return T-account totals and balancing entries using conventional To/By sides.

    A debit balance is carried down on the credit side and brought down on the debit
    side; a credit balance follows the opposite convention.
    """
    debit = money(total_debit, "total debit")
    credit = money(total_credit, "total credit")
    if debit > credit:
        balance = debit - credit
        side = "debit"
        balance_c_d_side = "credit"
        balance_b_d_side = "debit"
    elif credit > debit:
        balance = credit - debit
        side = "credit"
        balance_c_d_side = "debit"
        balance_b_d_side = "credit"
    else:
        balance = ZERO
        side = "zero"
        balance_c_d_side = None
        balance_b_d_side = None
    return {
        "total_debit": debit,
        "total_credit": credit,
        "balance": balance,
        "balance_side": side,
        "balance_c_d_side": balance_c_d_side,
        "balance_b_d_side": balance_b_d_side,
    }


def validate_educational_narration(narration: str,
                                  required_keywords: Iterable[str] = ()) -> dict:
    """Apply the reference simulator's narration style to learning exercises only.

    This deliberately does not run as part of validate_journal_entry(), so legitimate
    business entries are not rejected merely for not starting with 'Being'.
    """
    errors = []
    if not isinstance(narration, str) or not narration.strip():
        return {"is_valid": False, "errors": ["Narration is required."]}
    normalized = narration.strip()
    if not normalized.lower().startswith("being "):
        errors.append("Narration must begin with 'Being '.")
    if len(normalized.split()) < 5:
        errors.append("Narration must contain at least five words.")
    lowered = normalized.casefold()
    for keyword in required_keywords:
        if not isinstance(keyword, str) or not keyword.strip():
            continue
        if keyword.strip().casefold() not in lowered:
            errors.append(f"Narration must mention '{keyword.strip()}'.")
    return {"is_valid": not errors, "errors": errors}


def build_cash_book(
    opening_balance: Decimal | int | float | str,
    receipts: Iterable[dict],
    payments: Iterable[dict],
) -> dict:
    """Build a simple cash book and reject invalid transactions or cash overdrafts.

    Each transaction is a mapping with a non-empty description and positive amount.
    This is an educational calculation helper, not a persisted accounting record.
    """
    opening = money(opening_balance, "opening balance")
    receipt_rows = _cash_book_rows(receipts, "receipt")
    payment_rows = _cash_book_rows(payments, "payment")
    total_receipts = sum((row["amount"] for row in receipt_rows), ZERO)
    total_payments = sum((row["amount"] for row in payment_rows), ZERO)
    available_cash = opening + total_receipts
    if total_payments > available_cash:
        raise ValueError(
            "Cash payments exceed opening balance plus receipts; cash cannot be negative."
        )
    return {
        "opening_balance": opening,
        "receipts": receipt_rows,
        "payments": payment_rows,
        "total_receipts": total_receipts,
        "total_payments": total_payments,
        "closing_balance": available_cash - total_payments,
    }


def _cash_book_rows(transactions: Iterable[dict], label: str) -> list[dict]:
    """Validate and normalize simple cash-book transactions."""
    if transactions is None:
        raise ValueError(f"{label}s must be an iterable of transactions.")
    rows = []
    try:
        for transaction in transactions:
            if not isinstance(transaction, dict):
                raise ValueError(f"Each {label} must be a transaction mapping.")
            description = transaction.get("description")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"Each {label} must have a non-empty description.")
            amount = money(transaction.get("amount"), f"{label} amount")
            if amount <= ZERO:
                raise ValueError(f"Each {label} amount must be greater than zero.")
            rows.append({"description": description.strip(), "amount": amount})
    except TypeError:
        raise ValueError(f"{label}s must be an iterable of transactions.") from None
    return rows

