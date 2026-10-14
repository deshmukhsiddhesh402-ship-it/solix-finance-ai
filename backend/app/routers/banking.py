"""Module 4: Banking — tenant-authorized reconciliation API."""
import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator

from app.services.banking_engine import BankLine, BookLine, reconcile, reconciled_balance
from app.routers.enterprise import require_permission

router = APIRouter()


class BankLineIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    txn_date: date
    description: str = Field(max_length=2000)
    amount: float = Field(gt=0)
    txn_type: Literal["credit", "debit"]
    mode: str = Field(default="", max_length=64)

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Transaction amount must be finite.")
        return value


class BookLineIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    txn_date: date
    description: str = Field(max_length=2000)
    amount: float = Field(gt=0)
    txn_type: Literal["credit", "debit"]

    @field_validator("amount")
    @classmethod
    def amount_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Transaction amount must be finite.")
        return value


class ReconcileRequest(BaseModel):
    bank_lines: list[BankLineIn] = Field(max_length=10000)
    book_lines: list[BookLineIn] = Field(max_length=10000)
    date_window_days: int = Field(default=5, ge=0, le=31)
    balance_as_per_bank: float = 0.0

    @field_validator("balance_as_per_bank")
    @classmethod
    def bank_balance_must_be_finite(cls, value: float) -> float:
        # Negative balances are valid for overdrafts; NaN/Infinity are not.
        if not math.isfinite(value):
            raise ValueError("Bank balance must be finite.")
        return value


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
