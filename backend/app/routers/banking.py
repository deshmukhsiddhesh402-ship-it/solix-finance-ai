"""Module 4: Banking — tenant-authorized reconciliation API."""
import uuid
from datetime import date
from typing import Literal
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.core.db import get_db
from app.services.banking_engine import BankLine, BookLine, reconcile, reconciled_balance
from app.routers.enterprise import require_permission

router = APIRouter()

def _mask_bank_account_number(account_no: str | None) -> str | None:
    if account_no is None:
        return None
    normalized = str(account_no).strip()
    if not normalized:
        return None
    return f"****{normalized[-4:]}" if len(normalized) > 4 else "****"


@router.get("/statements")
def list_bank_statements(
    org_id: str = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    txn_type: Literal["credit", "debit"] | None = Query(default=None),
    reconciled: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    """Return a bounded tenant-scoped bank statement register without exposing full account numbers."""
    try:
        org_uuid = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(422, detail="start_date must be on or before end_date.")

    from app.models.accounting import BankStatement

    statement_query = db.query(BankStatement).filter(BankStatement.org_id == org_uuid)
    count_query = db.query(func.count(BankStatement.id)).filter(BankStatement.org_id == org_uuid)
    # Apply identical filters to both queries so count and page totals agree.
    if start_date is not None:
        statement_query = statement_query.filter(BankStatement.txn_date >= start_date)
        count_query = count_query.filter(BankStatement.txn_date >= start_date)
    if end_date is not None:
        statement_query = statement_query.filter(BankStatement.txn_date <= end_date)
        count_query = count_query.filter(BankStatement.txn_date <= end_date)
    if txn_type is not None:
        statement_query = statement_query.filter(BankStatement.txn_type == txn_type)
        count_query = count_query.filter(BankStatement.txn_type == txn_type)
    if reconciled is not None:
        statement_query = statement_query.filter(BankStatement.reconciled.is_(reconciled))
        count_query = count_query.filter(BankStatement.reconciled.is_(reconciled))

    total = count_query.scalar() or 0
    rows = (
        statement_query
        .order_by(BankStatement.txn_date.desc(), BankStatement.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "statements": [
            {
                "id": str(row.id),
                "bank_name": row.bank_name,
                "account_no_masked": _mask_bank_account_number(row.account_no),
                "txn_date": row.txn_date.isoformat(),
                "description": row.description,
                "amount": float(row.amount),
                "txn_type": row.txn_type,
                "mode": row.mode,
                "reconciled": bool(row.reconciled),
                "matched_journal_id": str(row.matched_journal_id) if row.matched_journal_id else None,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


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
