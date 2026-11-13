"""
Module 2: Accounting — API layer over accounting_engine.py
"""
import math
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal

from app.core.db import get_db
from app.routers.enterprise import require_permission
from app.services.accounting_engine import (
    LedgerLine, build_trial_balance, build_profit_and_loss, build_balance_sheet,
    financial_ratios, straight_line_depreciation, wdv_depreciation_schedule,
    InventoryTxn, inventory_valuation, inventory_valuation_decimal,
)

router = APIRouter()


def _inventory_valuation_payload(txns, method: str) -> dict:
    """Keep legacy rounded numbers while exposing high-precision Decimal strings."""
    rounded = inventory_valuation(txns, method)
    exact = inventory_valuation_decimal(txns, method)
    rounded["decimal"] = {
        "closing_quantity": format(exact["closing_quantity"], "f"),
        "closing_inventory_value": format(exact["closing_inventory_value"], "f"),
        "cogs": format(exact["cogs"], "f"),
    }
    return rounded

@router.get("/inventory/items/{item_id}/transactions")
def list_inventory_item_transactions(
    item_id: str,
    org_id: str = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    txn_type: Literal["purchase", "sale"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("journal_entry", "view")),
):
    """Return a tenant-verified inventory item's transaction ledger."""
    try:
        org_uuid = uuid.UUID(str(org_id))
        item_uuid = uuid.UUID(str(item_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or inventory item identifier.") from exc
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(422, detail="start_date must be on or before end_date.")

    from app.models.accounting import InventoryItem, InventoryTransaction

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_uuid, InventoryItem.org_id == org_uuid)
        .first()
    )
    if not item:
        raise HTTPException(404, detail="Inventory item not found.")

    transaction_query = db.query(InventoryTransaction).filter(
        InventoryTransaction.item_id == item_uuid
    )
    count_query = db.query(func.count(InventoryTransaction.id)).filter(
        InventoryTransaction.item_id == item_uuid
    )
    if start_date is not None:
        transaction_query = transaction_query.filter(InventoryTransaction.txn_date >= start_date)
        count_query = count_query.filter(InventoryTransaction.txn_date >= start_date)
    if end_date is not None:
        transaction_query = transaction_query.filter(InventoryTransaction.txn_date <= end_date)
        count_query = count_query.filter(InventoryTransaction.txn_date <= end_date)
    if txn_type is not None:
        transaction_query = transaction_query.filter(InventoryTransaction.txn_type == txn_type)
        count_query = count_query.filter(InventoryTransaction.txn_type == txn_type)

    total = count_query.scalar() or 0
    rows = (
        transaction_query
        .order_by(InventoryTransaction.txn_date.asc(), InventoryTransaction.sequence_no.asc(), InventoryTransaction.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "transactions": [
            {
                "id": str(row.id),
                "txn_type": row.txn_type,
                "txn_date": row.txn_date.isoformat(),
                "quantity": float(row.quantity),
                "unit_cost": float(row.unit_cost) if row.unit_cost is not None else None,
                "sequence_no": int(row.sequence_no),
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "ordering_note": "Transactions are ordered by transaction date, then database-generated insertion sequence. Existing rows receive sequence values during migration; their historical same-day business order cannot be reconstructed.",
    }


class InventoryTransactionCreate(BaseModel):
    txn_type: Literal["purchase", "sale"]
    txn_date: date
    quantity: Decimal = Field(gt=0, max_digits=18, decimal_places=4)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    reference_no: str = Field(min_length=1, max_length=100)

    @field_validator("quantity", "unit_cost", mode="before")
    @classmethod
    def reject_boolean_amounts(cls, value):
        if isinstance(value, bool):
            raise ValueError("Inventory amounts must be numeric values, not booleans.")
        return value

    @model_validator(mode="after")
    def validate_transaction_shape(self):
        self.reference_no = self.reference_no.strip()
        if not self.reference_no:
            raise ValueError("reference_no must not be blank.")
        if self.txn_type == "purchase" and self.unit_cost is None:
            raise ValueError("Purchase transactions require unit_cost.")
        if self.txn_type == "sale" and self.unit_cost is not None:
            raise ValueError("Sale transactions must omit unit_cost; costing is calculated from inventory layers.")
        return self


@router.post("/inventory/items/{item_id}/transactions", status_code=201)
def create_inventory_item_transaction(
    item_id: str,
    payload: InventoryTransactionCreate,
    org_id: str = Query(...),
    db=Depends(get_db),
    _user: str = Depends(require_permission("inventory", "create")),
):
    """Post a human-entered inventory movement with tenant, duplicate, and stock checks."""
    try:
        org_uuid = uuid.UUID(str(org_id))
        item_uuid = uuid.UUID(str(item_id))
        user_uuid = uuid.UUID(str(_user))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization, item, or user identifier.") from exc

    from app.models.accounting import InventoryItem, InventoryTransaction
    from app.models.enterprise import AuditLog

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_uuid, InventoryItem.org_id == org_uuid)
        .with_for_update()
        .first()
    )
    if not item:
        db.rollback()
        raise HTTPException(404, detail="Inventory item not found.")

    duplicate = (
        db.query(InventoryTransaction)
        .filter(
            InventoryTransaction.item_id == item_uuid,
            InventoryTransaction.reference_no == payload.reference_no,
        )
        .first()
    )
    if duplicate:
        db.rollback()
        raise HTTPException(409, detail="An inventory transaction with this reference already exists for the item.")

    transaction = InventoryTransaction(
        item_id=item_uuid,
        txn_type=payload.txn_type,
        txn_date=payload.txn_date,
        quantity=payload.quantity,
        unit_cost=payload.unit_cost,
        reference_no=payload.reference_no,
    )
    db.add(transaction)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="An inventory transaction with this reference already exists for the item.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, detail="Inventory transaction could not be prepared.") from exc

    rows = (
        db.query(InventoryTransaction)
        .filter(InventoryTransaction.item_id == item_uuid)
        .order_by(
            InventoryTransaction.txn_date.asc(),
            InventoryTransaction.sequence_no.asc(),
            InventoryTransaction.id.asc(),
        )
        .all()
    )
    transactions = [
        InventoryTxn(
            txn_type=row.txn_type,
            quantity=row.quantity,
            unit_cost=row.unit_cost if row.unit_cost is not None else Decimal("0"),
        )
        for row in rows
    ]
    try:
        valuation = _inventory_valuation_payload(transactions, item.costing_method)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, detail="Inventory transaction would produce an invalid stock valuation.") from exc

    db.add(AuditLog(
        org_id=org_uuid,
        user_id=user_uuid,
        action="create",
        entity_type="inventory_transaction",
        entity_id=str(transaction.id),
        changes={
            "reference_no": payload.reference_no,
            "txn_type": payload.txn_type,
            "txn_date": payload.txn_date.isoformat(),
            "quantity": str(payload.quantity),
            "unit_cost": str(payload.unit_cost) if payload.unit_cost is not None else None,
        },
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, detail="An inventory transaction with this reference already exists for the item.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, detail="Inventory transaction could not be posted.") from exc

    return {
        "transaction_id": str(transaction.id),
        "reference_no": transaction.reference_no,
        "sequence_no": int(transaction.sequence_no),
        "valuation": valuation,
        "message": "Inventory transaction posted successfully.",
    }


@router.get("/inventory/items")
def list_inventory_items(
    org_id: str = Query(...),
    costing_method: Literal["FIFO", "LIFO", "WAVG"] | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("journal_entry", "view")),
):
    """Return a tenant-scoped inventory item register with bounded search and pagination."""
    try:
        org_uuid = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    search_term = search.strip() if search is not None else None
    if search is not None and not search_term:
        raise HTTPException(422, detail="search must not be blank.")

    from app.models.accounting import InventoryItem

    item_query = db.query(InventoryItem).filter(InventoryItem.org_id == org_uuid)
    count_query = db.query(func.count(InventoryItem.id)).filter(InventoryItem.org_id == org_uuid)
    if costing_method is not None:
        item_query = item_query.filter(InventoryItem.costing_method == costing_method)
        count_query = count_query.filter(InventoryItem.costing_method == costing_method)
    if search_term is not None:
        pattern = f"%{search_term}%"
        criterion = or_(InventoryItem.sku.ilike(pattern), InventoryItem.name.ilike(pattern))
        item_query = item_query.filter(criterion)
        count_query = count_query.filter(criterion)

    total = count_query.scalar() or 0
    rows = (
        item_query
        .order_by(InventoryItem.sku.asc(), InventoryItem.name.asc(), InventoryItem.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": str(item.id),
                "sku": item.sku,
                "name": item.name,
                "costing_method": item.costing_method,
            }
            for item in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _new_account_code(account_name: str) -> str:
    """Generate a compact, collision-resistant code for auto-created ledger accounts.

    Human-readable prefixes alone are unsafe because different account names
    can share the same first characters while the database requires
    UNIQUE (org_id, code).
    """
    prefix = "".join(char for char in account_name.upper() if char.isalnum())[:5] or "ACCT"
    return f"{prefix}-{uuid.uuid4().hex[:14].upper()}"



class LedgerLineIn(BaseModel):
    account_name: str = Field(min_length=1, max_length=255)
    account_type: Literal["asset", "liability", "equity", "income", "expense"]
    debit: float = Field(default=0.0, ge=0)
    credit: float = Field(default=0.0, ge=0)
    gst_rate_pct: float | None = Field(default=None, ge=0, le=100)
    gst_type: Literal["IGST", "CGST", "SGST", "NONE"] | None = None
    gst_taxable_value: float | None = Field(default=None, ge=0)
    tds_section: str | None = Field(default=None, min_length=3, max_length=10)
    tds_rate: float | None = Field(default=None, ge=0, le=100)
    tds_amount: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_one_positive_side(self):
        numeric_values = {
            "debit": self.debit,
            "credit": self.credit,
            "gst_rate_pct": self.gst_rate_pct,
            "gst_taxable_value": self.gst_taxable_value,
            "tds_rate": self.tds_rate,
            "tds_amount": self.tds_amount,
        }
        for field_name, value in numeric_values.items():
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite.")
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("Each journal line must have a positive amount on exactly one side.")
        return self




@router.post("/journal-entries")
def create_journal_entry(
    entry_date: str = Query(...), narration: str = Query(..., min_length=1, max_length=2000),
    lines: list[LedgerLineIn] = Body(..., min_length=2, max_length=500),
    org_id: str = Query(...), db=Depends(get_db),
    _user: str = Depends(require_permission("journal_entry", "create")),
):
    """Persist a journal entry to the database — this is what makes the
    Live Dashboard 'live': previously, every /api/accounting endpoint below
    was stateless (compute-and-return, nothing saved). Data posted here is
    what app.routers.dashboard queries for real KPIs and trend charts.
    Uses a simple get-or-create on chart_of_accounts by (org_id, name) so
    you don't have to pre-provision accounts before posting entries.
    """
    from app.models.accounting import JournalEntry, JournalLine, ChartOfAccount

    try:
        org_uuid = uuid.UUID(str(org_id))
        user_uuid = uuid.UUID(str(_user))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or user identifier.") from exc

    from datetime import date as date_type
    try:
        parsed_entry_date = date_type.fromisoformat(entry_date)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, detail="entry_date must be a valid ISO date (YYYY-MM-DD).") from exc

    lines_dec = [LedgerLine(**l.dict()) for l in lines]
    if len(lines_dec) < 2:
        raise HTTPException(422, detail="A journal entry requires at least two lines.")
    tb_check = build_trial_balance(lines_dec)
    if not tb_check["is_balanced"]:
        raise HTTPException(422, detail="Journal entry does not balance (total debits != total credits).")

    entry = JournalEntry(org_id=org_uuid, entry_date=parsed_entry_date, narration=narration, created_by=user_uuid)
    db.add(entry)
    db.flush()

    for line in lines:
        account = (
            db.query(ChartOfAccount)
            .filter(ChartOfAccount.org_id == org_uuid, ChartOfAccount.name == line.account_name)
            .first()
        )
        if account and account.account_type != line.account_type:
            raise HTTPException(422, detail="Account name already exists with a different account type.")
        if not account:
            account = ChartOfAccount(
                org_id=org_uuid, code=_new_account_code(line.account_name),
                name=line.account_name, account_type=line.account_type,
            )
            db.add(account)
            db.flush()
        db.add(JournalLine(
            journal_id=entry.id, account_id=account.id, debit=line.debit, credit=line.credit,
            gst_rate_pct=line.gst_rate_pct, gst_type=line.gst_type, gst_taxable_value=line.gst_taxable_value,
            tds_section=line.tds_section, tds_rate=line.tds_rate, tds_amount=line.tds_amount,
        ))

    from app.models.enterprise import AuditLog
    db.add(AuditLog(
        org_id=org_uuid, user_id=user_uuid, action="create",
        entity_type="journal_entry", entity_id=str(entry.id),
        changes={"entry_date": entry.entry_date.isoformat(), "line_count": len(lines)},
    ))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, detail="Journal entry could not be posted.") from exc
    return {"journal_entry_id": str(entry.id), "message": "Journal entry posted successfully."}




@router.get("/inventory/items/{item_id}/valuation")
def persisted_inventory_item_valuation(
    item_id: str,
    org_id: str = Query(...),
    db=Depends(get_db),
    _user: str = Depends(require_permission("journal_entry", "view")),
):
    """Calculate a persisted inventory item's valuation from its tenant-owned transactions."""
    try:
        org_uuid = uuid.UUID(str(org_id))
        item_uuid = uuid.UUID(str(item_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or inventory item identifier.") from exc

    from app.models.accounting import InventoryItem, InventoryTransaction

    item = (
        db.query(InventoryItem)
        .filter(InventoryItem.id == item_uuid, InventoryItem.org_id == org_uuid)
        .first()
    )
    if not item:
        raise HTTPException(404, detail="Inventory item not found.")

    rows = (
        db.query(InventoryTransaction)
        .filter(InventoryTransaction.item_id == item_uuid)
        .order_by(InventoryTransaction.txn_date.asc(), InventoryTransaction.sequence_no.asc(), InventoryTransaction.id.asc())
        .all()
    )
    transactions = [
        InventoryTxn(
            txn_type=row.txn_type,
            quantity=row.quantity,
            unit_cost=row.unit_cost if row.unit_cost is not None else Decimal("0"),
        )
        for row in rows
    ]
    try:
        valuation = _inventory_valuation_payload(transactions, item.costing_method)
    except ValueError as exc:
        raise HTTPException(422, detail="Stored inventory transactions cannot be valued. Review the item ledger.") from exc

    return {
        "item": {
            "id": str(item.id),
            "sku": item.sku,
            "name": item.name,
            "costing_method": item.costing_method,
        },
        "transaction_count": len(transactions),
        "valuation": valuation,
        "ordering_note": "Valuation processes transactions by transaction date, then database-generated insertion sequence. Historical same-day business order cannot be reconstructed for records created before this sequence was added.",
    }


@router.get("/fixed-assets")
def list_fixed_assets(
    org_id: str = Query(...),
    purchase_date_from: date | None = Query(default=None),
    purchase_date_to: date | None = Query(default=None),
    depreciation_method: Literal["straight_line", "wdv"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("journal_entry", "view")),
):
    """Return a tenant-scoped fixed-asset register with bounded pagination."""
    try:
        org_uuid = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    if purchase_date_from and purchase_date_to and purchase_date_from > purchase_date_to:
        raise HTTPException(422, detail="purchase_date_from must be on or before purchase_date_to.")

    from app.models.accounting import FixedAsset

    asset_query = db.query(FixedAsset).filter(FixedAsset.org_id == org_uuid)
    count_query = db.query(func.count(FixedAsset.id)).filter(FixedAsset.org_id == org_uuid)
    if purchase_date_from is not None:
        asset_query = asset_query.filter(FixedAsset.purchase_date >= purchase_date_from)
        count_query = count_query.filter(FixedAsset.purchase_date >= purchase_date_from)
    if purchase_date_to is not None:
        asset_query = asset_query.filter(FixedAsset.purchase_date <= purchase_date_to)
        count_query = count_query.filter(FixedAsset.purchase_date <= purchase_date_to)
    if depreciation_method is not None:
        asset_query = asset_query.filter(FixedAsset.depreciation_method == depreciation_method)
        count_query = count_query.filter(FixedAsset.depreciation_method == depreciation_method)

    total = count_query.scalar() or 0
    rows = (
        asset_query
        .order_by(FixedAsset.purchase_date.desc(), FixedAsset.asset_name.asc(), FixedAsset.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "assets": [
            {
                "id": str(asset.id),
                "asset_name": asset.asset_name,
                "purchase_date": asset.purchase_date.isoformat(),
                "cost": float(asset.cost),
                "salvage_value": float(asset.salvage_value),
                "useful_life_years": asset.useful_life_years,
                "depreciation_method": asset.depreciation_method,
            }
            for asset in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/chart-of-accounts")
def list_chart_of_accounts(
    org_id: str = Query(...),
    account_type: Literal["asset", "liability", "equity", "income", "expense"] | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("journal_entry", "view")),
):
    """Return a bounded, tenant-scoped chart-of-accounts register."""
    try:
        org_uuid = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc

    from app.models.accounting import ChartOfAccount

    account_query = db.query(ChartOfAccount).filter(ChartOfAccount.org_id == org_uuid)
    count_query = db.query(func.count(ChartOfAccount.id)).filter(ChartOfAccount.org_id == org_uuid)
    if account_type is not None:
        account_query = account_query.filter(ChartOfAccount.account_type == account_type)
        count_query = count_query.filter(ChartOfAccount.account_type == account_type)
    if not include_inactive:
        account_query = account_query.filter(ChartOfAccount.is_active.is_(True))
        count_query = count_query.filter(ChartOfAccount.is_active.is_(True))

    total = count_query.scalar() or 0
    rows = (
        account_query
        .order_by(ChartOfAccount.code.asc(), ChartOfAccount.name.asc(), ChartOfAccount.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "accounts": [
            {
                "id": str(account.id),
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
                "parent_id": str(account.parent_id) if account.parent_id else None,
                "is_active": bool(account.is_active),
            }
            for account in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/journal-entries")
def list_journal_entries(
    org_id: str = Query(...),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("journal_entry", "view")),
):
    """Return a tenant-scoped, stably paginated journal-entry register."""
    try:
        org_uuid = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, detail="start_date must be on or before end_date.")

    from app.models.accounting import JournalEntry, JournalLine, ChartOfAccount

    entry_query = db.query(JournalEntry).filter(JournalEntry.org_id == org_uuid)
    count_query = db.query(func.count(JournalEntry.id)).filter(JournalEntry.org_id == org_uuid)
    if start_date is not None:
        entry_query = entry_query.filter(JournalEntry.entry_date >= start_date)
        count_query = count_query.filter(JournalEntry.entry_date >= start_date)
    if end_date is not None:
        entry_query = entry_query.filter(JournalEntry.entry_date <= end_date)
        count_query = count_query.filter(JournalEntry.entry_date <= end_date)

    total = count_query.scalar() or 0
    entries = (
        entry_query
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc(), JournalEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    if not entries:
        return {"entries": [], "total": total, "limit": limit, "offset": offset}

    entry_ids = [entry.id for entry in entries]
    line_rows = (
        db.query(JournalLine, ChartOfAccount)
        .join(ChartOfAccount, ChartOfAccount.id == JournalLine.account_id)
        .filter(
            JournalLine.journal_id.in_(entry_ids),
            ChartOfAccount.org_id == org_uuid,
        )
        .order_by(JournalLine.id.asc())
        .all()
    )
    lines_by_entry: dict[uuid.UUID, list[dict]] = {}
    for line, account in line_rows:
        lines_by_entry.setdefault(line.journal_id, []).append({
            "account_name": account.name,
            "account_type": account.account_type,
            "debit": float(line.debit),
            "credit": float(line.credit),
            "gst_rate_pct": float(line.gst_rate_pct) if line.gst_rate_pct is not None else None,
            "gst_type": line.gst_type,
            "gst_taxable_value": float(line.gst_taxable_value) if line.gst_taxable_value is not None else None,
            "tds_section": line.tds_section,
            "tds_rate": float(line.tds_rate) if line.tds_rate is not None else None,
            "tds_amount": float(line.tds_amount) if line.tds_amount is not None else None,
        })

    return {
        "entries": [
            {
                "id": str(entry.id),
                "entry_date": entry.entry_date.isoformat(),
                "narration": entry.narration,
                "reference_no": entry.reference_no,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
                "lines": lines_by_entry.get(entry.id, []),
            }
            for entry in entries
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


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
    current_assets: float = Field(ge=0)
    current_liabilities: float = Field(ge=0)
    inventory: float = Field(ge=0)
    total_debt: float = Field(ge=0)
    total_equity: float = Field(ge=0)
    net_profit: float
    revenue: float = Field(ge=0)
    total_assets: float = Field(ge=0)

    @model_validator(mode="after")
    def require_finite_values(self):
        for name, value in self.__dict__.items():
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite.")
        return self


@router.post("/ratios")
def ratios(req: RatiosRequest):
    return financial_ratios(**req.dict())


class StraightLineRequest(BaseModel):
    cost: float = Field(ge=0)
    salvage: float = Field(ge=0)
    useful_life_years: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_inputs(self):
        if not all(math.isfinite(v) for v in (self.cost, self.salvage)):
            raise ValueError("cost and salvage must be finite.")
        if self.salvage > self.cost:
            raise ValueError("salvage cannot exceed cost.")
        return self


@router.post("/depreciation/straight-line")
def depreciation_straight_line(req: StraightLineRequest):
    return {"annual_depreciation": straight_line_depreciation(
        req.cost, req.salvage, req.useful_life_years)}


class WdvRequest(BaseModel):
    cost: float = Field(ge=0)
    rate_pct: float = Field(gt=0, le=100)
    years: int = Field(ge=1)

    @model_validator(mode="after")
    def require_finite_values(self):
        if not all(math.isfinite(v) for v in (self.cost, self.rate_pct)):
            raise ValueError("cost and rate_pct must be finite.")
        return self


@router.post("/depreciation/wdv")
def depreciation_wdv(req: WdvRequest):
    return {"schedule": wdv_depreciation_schedule(req.cost, req.rate_pct, req.years)}


class InventoryTxnIn(BaseModel):
    txn_type: Literal["purchase", "sale"]
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)

    @model_validator(mode="after")
    def require_finite_values(self):
        if not all(math.isfinite(v) for v in (self.quantity, self.unit_cost)):
            raise ValueError("quantity and unit_cost must be finite.")
        return self


class InventoryValuationRequest(BaseModel):
    txns: list[InventoryTxnIn]
    method: Literal["FIFO", "LIFO", "WAVG"]


@router.post("/inventory/valuation")
def inventory_valuation_endpoint(req: InventoryValuationRequest):
    txns = [InventoryTxn(**t.dict()) for t in req.txns]
    return _inventory_valuation_payload(txns, req.method)
