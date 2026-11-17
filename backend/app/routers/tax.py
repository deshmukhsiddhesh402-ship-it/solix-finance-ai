"""
Module 3: Indian Tax — API layer over tax_engine.py
"""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.tax_engine import (
    calculate_gst, GstInvoiceLine, gstr3b_summary, calculate_tds,
    calculate_income_tax_new_regime,
)

router = APIRouter()


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
    # Backward-compatible default; unsupported years are rejected by the API schema.
    financial_year: Literal["2025-26"] = "2025-26"


@router.post("/income-tax/new-regime")
def income_tax_new_regime(req: IncomeTaxRequest):
    result = calculate_income_tax_new_regime(
        req.gross_salary, req.other_income, financial_year=req.financial_year
    )
    return {
        **result,
        "calculation_status": "reference_only",
        "filing_ready": False,
    }
