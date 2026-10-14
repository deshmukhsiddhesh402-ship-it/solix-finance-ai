"""Module 4: Banking — tenant-authorized reconciliation API."""
import math
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator

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

    @model_validator(mode="after")
    def transaction_ids_must_be_unique_per_source(self):
        for source_name, lines in (
            ("bank_lines", self.bank_lines),
            ("book_lines", self.book_lines),
        ):
            ids = [line.id for line in lines]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Transaction IDs in {source_name} must be unique.")
        return self


@router.post("/reconcile")
def reconcile_endpoint(
    req: ReconcileRequest,
    org_id: str = Query(...),
    _user: str = Depends(require_permission("reports", "create")),
):
    bank_lines = [BankLine(**l.model_dump()) for l in req.bank_lines]
    book_lines = [BookLine(**l.model_dump()) for l in req.book_lines]
    try:
        result = reconcile(bank_lines, book_lines, req.date_window_days)
        balance_as_per_books = reconciled_balance(
            req.balance_as_per_bank,
            result["totals"]["outstanding_cheques"],
            result["totals"]["deposits_not_credited"],
        )
    except ValueError as exc:
        # Finite individual values can still overflow when aggregated. Return a
        # client error instead of leaking a 500 for a mathematically invalid request.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result["reconciliation_statement"] = {
        "balance_as_per_bank": req.balance_as_per_bank,
        "add_deposits_not_credited": result["totals"]["deposits_not_credited"],
        "less_outstanding_cheques": result["totals"]["outstanding_cheques"],
        "balance_as_per_books": balance_as_per_books,
    }
    return result
