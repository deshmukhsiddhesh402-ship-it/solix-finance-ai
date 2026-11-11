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
