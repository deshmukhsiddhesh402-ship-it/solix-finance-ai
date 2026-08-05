"""
Module 4: Banking — API layer over banking_engine.py
"""
from datetime import date
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.banking_engine import BankLine, BookLine, reconcile, reconciled_balance

router = APIRouter()


class BankLineIn(BaseModel):
    id: str
    txn_date: date
    description: str
    amount: float
    txn_type: Literal["credit", "debit"]
    mode: str = ""


class BookLineIn(BaseModel):
    id: str
    txn_date: date
    description: str
    amount: float
    txn_type: Literal["credit", "debit"]


class ReconcileRequest(BaseModel):
    bank_lines: list[BankLineIn]
    book_lines: list[BookLineIn]
    date_window_days: int = 5
    balance_as_per_bank: float = 0.0


@router.post("/reconcile")
def reconcile_endpoint(req: ReconcileRequest):
    bank_lines = [BankLine(**l.dict()) for l in req.bank_lines]
    book_lines = [BookLine(**l.dict()) for l in req.book_lines]
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
