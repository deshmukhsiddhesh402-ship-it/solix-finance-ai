"""Module 4: Banking — tenant-authorized reconciliation API."""
from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, model_validator
from app.services.banking_engine import BankLine, BookLine, reconcile, reconciled_balance
from app.routers.enterprise import require_permission

router = APIRouter()


def _reject_boolean_numeric_inputs(values, field_names):
    """Prevent Pydantic from coercing JSON booleans into reconciliation amounts."""
    if isinstance(values, dict):
        for field_name in field_names:
            if isinstance(values.get(field_name), bool):
                raise ValueError(f"{field_name} must be numeric, not boolean.")
    return values


class BankLineIn(BaseModel):
    id: str
    txn_date: date
    description: str
    amount: float
    txn_type: Literal["credit", "debit"]
    mode: str = ""

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_amount(cls, values):
        return _reject_boolean_numeric_inputs(values, ("amount",))


class BookLineIn(BaseModel):
    id: str
    txn_date: date
    description: str
    amount: float
    txn_type: Literal["credit", "debit"]

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_amount(cls, values):
        return _reject_boolean_numeric_inputs(values, ("amount",))


class ReconcileRequest(BaseModel):
    bank_lines: list[BankLineIn]
    book_lines: list[BookLineIn]
    date_window_days: int = 5
    balance_as_per_bank: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def reject_boolean_numeric_inputs(cls, values):
        return _reject_boolean_numeric_inputs(values, ("date_window_days", "balance_as_per_bank"))

@router.post("/reconcile")
def reconcile_endpoint(
    req: ReconcileRequest,
    org_id: str = Query(...),
    _user: str = Depends(require_permission("reports", "create")),
):
    bank_lines = [BankLine(**l.dict()) for l in req.bank_lines]
    book_lines = [BookLine(**l.dict()) for l in req.book_lines]
    result = reconcile(bank_lines, book_lines, req.date_window_days)
    result["reconciliation_statement"] = {
        "balance_as_per_bank": req.balance_as_per_bank,
        "add_deposits_not_credited": result["totals"]["deposits_not_credited"],
        "less_outstanding_cheques": result["totals"]["outstanding_cheques"],
        "balance_as_per_books": reconciled_balance(req.balance_as_per_bank, result["totals"]["outstanding_cheques"], result["totals"]["deposits_not_credited"]),
    }
    return result
