"""
Module 3: Indian Tax — API layer over tax_engine.py
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.tax_engine import (
    calculate_gst, GstInvoiceLine, gstr3b_summary, calculate_tds,
    calculate_income_tax_new_regime,
)

router = APIRouter()


class GstRequest(BaseModel):
    taxable_value: float = Field(ge=0, allow_inf_nan=False)
    gst_rate_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    is_interstate: bool


@router.post("/gst/calculate")
def gst_calculate(req: GstRequest):
    return calculate_gst(req.taxable_value, req.gst_rate_pct, req.is_interstate)


class GstInvoiceLineIn(BaseModel):
    taxable_value: float = Field(ge=0, allow_inf_nan=False)
    gst_rate_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    is_interstate: bool


class Gstr3bRequest(BaseModel):
    lines: list[GstInvoiceLineIn] = Field(max_length=5000)
    input_tax_credit: float = Field(default=0.0, ge=0, allow_inf_nan=False)


@router.post("/gst/gstr3b-summary")
def gst_gstr3b(req: Gstr3bRequest):
    lines = [GstInvoiceLine(**l.dict()) for l in req.lines]
    try:
        return gstr3b_summary(lines, req.input_tax_credit)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e


class TdsRequest(BaseModel):
    amount_paid: float = Field(ge=0, allow_inf_nan=False)
    section: str = Field(min_length=1, max_length=10)
    has_pan: bool = True


@router.post("/tds/calculate")
def tds_calculate(req: TdsRequest):
    try:
        return calculate_tds(req.amount_paid, req.section, req.has_pan)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e


class IncomeTaxRequest(BaseModel):
    gross_salary: float = Field(ge=0, allow_inf_nan=False)
    other_income: float = Field(default=0.0, ge=0, allow_inf_nan=False)


@router.post("/income-tax/new-regime")
def income_tax_new_regime(req: IncomeTaxRequest):
    try:
        return calculate_income_tax_new_regime(req.gross_salary, req.other_income)
    except ValueError as e:
        raise HTTPException(422, detail=str(e)) from e
