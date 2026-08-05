"""
Module 2: Accounting — API layer over accounting_engine.py
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal

from app.core.db import get_db
from app.services.accounting_engine import (
    LedgerLine, build_trial_balance, build_profit_and_loss, build_balance_sheet,
    financial_ratios, straight_line_depreciation, wdv_depreciation_schedule,
    InventoryTxn, inventory_valuation,
)

router = APIRouter()


@router.post("/journal-entries")
def create_journal_entry(
    entry_date: str, narration: str, lines: list[LedgerLineIn],
    org_id: str | None = None, db=Depends(get_db),
):
    """Persist a journal entry to the database — this is what makes the
    Live Dashboard 'live': previously, every /api/accounting endpoint below
    was stateless (compute-and-return, nothing saved). Data posted here is
    what app.routers.dashboard queries for real KPIs and trend charts.
    Uses a simple get-or-create on chart_of_accounts by (org_id, name) so
    you don't have to pre-provision accounts before posting entries.
    """
    from datetime import date as date_type
    from app.models.accounting import JournalEntry, JournalLine, ChartOfAccount

    lines_dec = [LedgerLine(**l.dict()) for l in lines]
    tb_check = build_trial_balance(lines_dec)
    if not tb_check["is_balanced"]:
        raise HTTPException(422, detail="Journal entry does not balance (total debits != total credits).")

    entry = JournalEntry(org_id=org_id, entry_date=date_type.fromisoformat(entry_date), narration=narration)
    db.add(entry)
    db.flush()

    for line in lines:
        account = (
            db.query(ChartOfAccount)
            .filter(ChartOfAccount.org_id == org_id, ChartOfAccount.name == line.account_name)
            .first()
        )
        if not account:
            account = ChartOfAccount(
                org_id=org_id, code=line.account_name[:10].upper(),
                name=line.account_name, account_type=line.account_type,
            )
            db.add(account)
            db.flush()
        db.add(JournalLine(journal_id=entry.id, account_id=account.id, debit=line.debit, credit=line.credit))

    db.commit()
    return {"journal_entry_id": str(entry.id), "message": "Journal entry posted successfully."}


class LedgerLineIn(BaseModel):
    account_name: str
    account_type: Literal["asset", "liability", "equity", "income", "expense"]
    debit: float = 0.0
    credit: float = 0.0


class TrialBalanceRequest(BaseModel):
    lines: list[LedgerLineIn]


@router.post("/trial-balance")
def trial_balance(req: TrialBalanceRequest):
    lines = [LedgerLine(**l.dict()) for l in req.lines]
    result = build_trial_balance(lines)
    if not result["is_balanced"]:
        raise HTTPException(422, detail="Books do not balance — check debit/credit entries.")
    return result


@router.post("/profit-and-loss")
def profit_and_loss(req: TrialBalanceRequest):
    lines = [LedgerLine(**l.dict()) for l in req.lines]
    tb = build_trial_balance(lines)
    return build_profit_and_loss(tb["rows"])


@router.post("/balance-sheet")
def balance_sheet(req: TrialBalanceRequest):
    lines = [LedgerLine(**l.dict()) for l in req.lines]
    tb = build_trial_balance(lines)
    pnl = build_profit_and_loss(tb["rows"])
    return build_balance_sheet(tb["rows"], pnl["net_profit"])


class RatiosRequest(BaseModel):
    current_assets: float
    current_liabilities: float
    inventory: float
    total_debt: float
    total_equity: float
    net_profit: float
    revenue: float
    total_assets: float


@router.post("/ratios")
def ratios(req: RatiosRequest):
    return financial_ratios(**req.dict())


class StraightLineRequest(BaseModel):
    cost: float
    salvage: float
    useful_life_years: int


@router.post("/depreciation/straight-line")
def depreciation_straight_line(req: StraightLineRequest):
    return {"annual_depreciation": straight_line_depreciation(
        req.cost, req.salvage, req.useful_life_years)}


class WdvRequest(BaseModel):
    cost: float
    rate_pct: float
    years: int


@router.post("/depreciation/wdv")
def depreciation_wdv(req: WdvRequest):
    return {"schedule": wdv_depreciation_schedule(req.cost, req.rate_pct, req.years)}


class InventoryTxnIn(BaseModel):
    txn_type: Literal["purchase", "sale"]
    quantity: float
    unit_cost: float = 0.0


class InventoryValuationRequest(BaseModel):
    txns: list[InventoryTxnIn]
    method: Literal["FIFO", "LIFO", "WAVG"]


@router.post("/inventory/valuation")
def inventory_valuation_endpoint(req: InventoryValuationRequest):
    txns = [InventoryTxn(**t.dict()) for t in req.txns]
    return inventory_valuation(txns, req.method)
