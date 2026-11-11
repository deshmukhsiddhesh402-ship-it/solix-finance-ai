"""
Module 3: Indian Tax — API layer over tax_engine.py
"""
import re
import uuid
from datetime import datetime
from typing import Literal
from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from app.core.db import get_db
from app.routers.enterprise import require_permission

from app.services.tax_engine import (
    calculate_gst, GstInvoiceLine, gstr3b_summary, calculate_tds,
    calculate_income_tax_new_regime,
)

router = APIRouter()

@router.get("/tds/entries")
def list_tds_entries(
    org_id: str = Query(...),
    section: str | None = Query(default=None, min_length=3, max_length=10),
    deposit_date_from: str | None = Query(default=None),
    deposit_date_to: str | None = Query(default=None),
    deposited: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    """Return tenant-scoped TDS entries while masking deductee PAN values."""
    try:
        org_uuid = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc

    parsed_from = None
    parsed_to = None
    try:
        if deposit_date_from is not None:
            parsed_from = datetime.strptime(deposit_date_from, "%Y-%m-%d").date()
            if parsed_from.isoformat() != deposit_date_from:
                raise ValueError("non-canonical date")
        if deposit_date_to is not None:
            parsed_to = datetime.strptime(deposit_date_to, "%Y-%m-%d").date()
            if parsed_to.isoformat() != deposit_date_to:
                raise ValueError("non-canonical date")
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, detail="Deposit date filters must use valid YYYY-MM-DD dates.") from exc
    if parsed_from is not None and parsed_to is not None and parsed_from > parsed_to:
        raise HTTPException(422, detail="deposit_date_from must be on or before deposit_date_to.")

    from app.models.tax import TDSEntry

    entry_query = db.query(TDSEntry).filter(TDSEntry.org_id == org_uuid)
    count_query = db.query(func.count(TDSEntry.id)).filter(TDSEntry.org_id == org_uuid)
    for query_name in ("entry_query", "count_query"):
        query = entry_query if query_name == "entry_query" else count_query
        if section is not None:
            query = query.filter(TDSEntry.section == section.strip().upper())
        if parsed_from is not None:
            query = query.filter(TDSEntry.deposit_date >= parsed_from)
        if parsed_to is not None:
            query = query.filter(TDSEntry.deposit_date <= parsed_to)
        if deposited is True:
            query = query.filter(TDSEntry.deposit_date.is_not(None))
        elif deposited is False:
            query = query.filter(TDSEntry.deposit_date.is_(None))
        if query_name == "entry_query":
            entry_query = query
        else:
            count_query = query

    total = count_query.scalar() or 0
    rows = (
        entry_query
        .order_by(TDSEntry.deposit_date.desc(), TDSEntry.section.asc(), TDSEntry.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "entries": [
            {
                "id": str(row.id),
                "section": row.section,
                "deductee_name": row.deductee_name,
                "deductee_pan_masked": _mask_deductee_pan(row.deductee_pan),
                "amount_paid": float(row.amount_paid),
                "tds_rate": float(row.tds_rate),
                "tds_amount": float(row.tds_amount),
                "deposit_date": row.deposit_date.isoformat() if row.deposit_date else None,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _mask_deductee_pan(pan: str | None) -> str | None:
    if pan is None:
        return None
    normalized = str(pan).strip().upper()
    if not normalized:
        return None
    if re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", normalized):
        return f"*****{normalized[-5:]}"
    # Malformed legacy values are not safe to partially disclose.
    return "**********"


def _validate_gst_period(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise HTTPException(422, detail=f"{label} must use YYYY-MM format.")
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(422, detail=f"{label} must be a valid calendar month.") from exc
    return value


@router.get("/gst/returns")
def list_gst_returns(
    org_id: str = Query(...),
    return_type: Literal["GSTR1", "GSTR3B", "GSTR9"] | None = Query(default=None),
    period_from: str | None = Query(default=None),
    period_to: str | None = Query(default=None),
    filed: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    db=Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    """Return a bounded tenant-scoped GST return register with filing metadata."""
    try:
        org_uuid = uuid.UUID(str(org_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc

    period_from = _validate_gst_period(period_from, "period_from")
    period_to = _validate_gst_period(period_to, "period_to")
    if period_from is not None and period_to is not None and period_from > period_to:
        raise HTTPException(422, detail="period_from must be on or before period_to.")

    from app.models.tax import GSTReturn

    return_query = db.query(GSTReturn).filter(GSTReturn.org_id == org_uuid)
    count_query = db.query(func.count(GSTReturn.id)).filter(GSTReturn.org_id == org_uuid)
    for query_name in ("return_query", "count_query"):
        query = return_query if query_name == "return_query" else count_query
        if return_type is not None:
            query = query.filter(GSTReturn.return_type == return_type)
        if period_from is not None:
            query = query.filter(GSTReturn.period >= period_from)
        if period_to is not None:
            query = query.filter(GSTReturn.period <= period_to)
        if filed is True:
            query = query.filter(GSTReturn.filed_at.is_not(None))
        elif filed is False:
            query = query.filter(GSTReturn.filed_at.is_(None))
        if query_name == "return_query":
            return_query = query
        else:
            count_query = query

    total = count_query.scalar() or 0
    rows = (
        return_query
        .order_by(GSTReturn.period.desc(), GSTReturn.return_type.asc(), GSTReturn.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "returns": [
            {
                "id": str(row.id),
                "return_type": row.return_type,
                "period": row.period,
                "total_taxable_value": float(row.total_taxable_value) if row.total_taxable_value is not None else None,
                "total_tax_liability": float(row.total_tax_liability) if row.total_tax_liability is not None else None,
                "filed_at": row.filed_at.isoformat() if row.filed_at else None,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }



class GstRequest(BaseModel):
    taxable_value: float
    gst_rate_pct: float
    is_interstate: bool


@router.post("/gst/calculate")
def gst_calculate(req: GstRequest):
    return calculate_gst(req.taxable_value, req.gst_rate_pct, req.is_interstate)


class GstInvoiceLineIn(BaseModel):
    taxable_value: float
    gst_rate_pct: float
    is_interstate: bool


class Gstr3bRequest(BaseModel):
    lines: list[GstInvoiceLineIn]
    input_tax_credit: float = 0.0


@router.post("/gst/gstr3b-summary")
def gst_gstr3b(req: Gstr3bRequest):
    lines = [GstInvoiceLine(**l.dict()) for l in req.lines]
    return gstr3b_summary(lines, req.input_tax_credit)


class TdsRequest(BaseModel):
    amount_paid: float
    section: str
    has_pan: bool = True


@router.post("/tds/calculate")
def tds_calculate(req: TdsRequest):
    try:
        return calculate_tds(req.amount_paid, req.section, req.has_pan)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))


class IncomeTaxRequest(BaseModel):
    gross_salary: float
    other_income: float = 0.0


@router.post("/income-tax/new-regime")
def income_tax_new_regime(req: IncomeTaxRequest):
    return calculate_income_tax_new_regime(req.gross_salary, req.other_income)
