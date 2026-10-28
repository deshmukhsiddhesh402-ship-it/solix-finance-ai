"""Module 4: Banking — tenant-authorized reconciliation API."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.services.banking_engine import BankLine, BookLine, reconcile, reconciled_balance
from app.routers.enterprise import require_permission

router = APIRouter()

# Keep reconciliation requests bounded: matching bank/book rows can be
# computationally expensive, and unbounded payloads invite resource exhaustion.
MAX_RECONCILIATION_LINES = 5000


class BankLineIn(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    txn_date: date
    description: str = Field(min_length=1, max_length=500)
    amount: float = Field(ge=0, allow_inf_nan=False)
    txn_type: Literal["credit", "debit"]
    mode: str = Field(default="", max_length=50)


class BookLineIn(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    txn_date: date
    description: str = Field(min_length=1, max_length=500)
    amount: float = Field(ge=0, allow_inf_nan=False)
    txn_type: Literal["credit", "debit"]


class ReconcileRequest(BaseModel):
    bank_lines: list[BankLineIn] = Field(max_length=MAX_RECONCILIATION_LINES)
    book_lines: list[BookLineIn] = Field(max_length=MAX_RECONCILIATION_LINES)
    date_window_days: int = Field(default=5, ge=0, le=31)
    balance_as_per_bank: float = Field(default=0.0, allow_inf_nan=False)


@router.post("/reconcile")
def reconcile_endpoint(
    req: ReconcileRequest,
    org_id: str = Query(...),
    _user: str = Depends(require_permission("reports", "create")),
):
    bank_lines = [BankLine(**l.model_dump()) for l in req.bank_lines]
    book_lines = [BookLine(**l.model_dump()) for l in req.book_lines]
    result = reconcile(bank_lines, book_lines, req.date_window_days)
    result["reconciliation_statement"] = {
        "balance_as_per_bank": req.balance_as_per_bank,
        "add_deposits_not_credited": result["totals"]["deposits_not_credited"],
        "less_outstanding_cheques": result["totals"]["outstanding_cheques"],
        "balance_as_per_books": reconciled_balance(
            req.balance_as_per_bank,
            result["totals"]["outstanding_cheques"],
            result["totals"]["deposits_not_credited"],
        ),
    }
    return result
