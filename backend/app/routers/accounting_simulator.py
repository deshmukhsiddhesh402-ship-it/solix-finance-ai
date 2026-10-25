"""Stateless API endpoints for accounting simulator practice.

These endpoints validate and calculate educational examples only. They do not
persist journals, post to the production ledger, or bypass existing auth/RBAC.
"""
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.accounting_simulator_engine import (
    JournalEntry,
    JournalLine,
    build_accounting_cycle,
    build_cash_book,
    validate_journal_entry,
)

router = APIRouter()


class JournalLineInput(BaseModel):
    account: str = Field(min_length=1, max_length=120)
    debit: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=14, decimal_places=2)


class JournalEntryInput(BaseModel):
    narration: str = Field(default="", max_length=500)
    lines: list[JournalLineInput] = Field(min_length=2, max_length=100)


class AccountingCycleRequest(BaseModel):
    entries: list[JournalEntryInput] = Field(min_length=1, max_length=200)


class CashTransactionInput(BaseModel):
    description: str = Field(min_length=1, max_length=160)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class CashBookRequest(BaseModel):
    opening_balance: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    receipts: list[CashTransactionInput] = Field(default_factory=list, max_length=500)
    payments: list[CashTransactionInput] = Field(default_factory=list, max_length=500)


def _to_journal_entry(item: JournalEntryInput) -> JournalEntry:
    return JournalEntry(
        narration=item.narration,
        lines=tuple(
            JournalLine(account=line.account, debit=line.debit, credit=line.credit)
            for line in item.lines
        ),
    )


def _raise_validation_error(exc: ValueError) -> None:
    raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/practice/journal-entry")
def validate_practice_journal(request: JournalEntryInput) -> dict[str, Any]:
    """Validate one in-memory practice entry; no database writes occur."""
    try:
        result = validate_journal_entry(_to_journal_entry(request))
    except ValueError as exc:
        _raise_validation_error(exc)
    return {
        "mode": "practice_only",
        "persisted": False,
        "narration": request.narration,
        **result,
    }


@router.post("/practice/accounting-cycle")
def calculate_practice_cycle(request: AccountingCycleRequest) -> dict[str, Any]:
    """Calculate journal-to-ledger-to-trial-balance results without persistence."""
    entries = [_to_journal_entry(item) for item in request.entries]
    try:
        result = build_accounting_cycle(entries)
    except ValueError as exc:
        _raise_validation_error(exc)
    return {"mode": "practice_only", "persisted": False, **result}


@router.post("/practice/cash-book")
def calculate_practice_cash_book(request: CashBookRequest) -> dict[str, Any]:
    """Calculate an educational cash book without creating accounting records."""
    try:
        result = build_cash_book(
            request.opening_balance,
            [item.model_dump() for item in request.receipts],
            [item.model_dump() for item in request.payments],
        )
    except ValueError as exc:
        _raise_validation_error(exc)
    return {"mode": "practice_only", "persisted": False, **result}
