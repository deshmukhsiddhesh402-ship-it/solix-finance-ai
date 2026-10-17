"""Regression tests for tax API validation and bounded GSTR-3B workloads."""
import os
import sys

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.tax import (
    GstRequest,
    GstInvoiceLineIn,
    Gstr3bRequest,
    IncomeTaxRequest,
    gst_calculate,
    gst_gstr3b,
    income_tax_new_regime,
)


def _line():
    return {"taxable_value": 1000, "gst_rate_pct": 18, "is_interstate": False}


def test_gstr3b_requires_at_least_one_line():
    with pytest.raises(ValidationError):
        Gstr3bRequest(lines=[])


def test_gstr3b_caps_lines_at_500():
    with pytest.raises(ValidationError):
        Gstr3bRequest(lines=[_line()] * 501)


def test_gstr3b_accepts_500_lines():
    req = Gstr3bRequest(lines=[_line()] * 500)
    assert len(req.lines) == 500


def test_gst_invalid_non_finite_amount_maps_to_422():
    req = GstRequest(taxable_value=float("inf"), gst_rate_pct=18, is_interstate=False)
    with pytest.raises(HTTPException) as exc:
        gst_calculate(req)
    assert exc.value.status_code == 422


def test_income_tax_invalid_non_finite_income_maps_to_422():
    req = IncomeTaxRequest(gross_salary=100000, other_income=float("nan"))
    with pytest.raises(HTTPException) as exc:
        income_tax_new_regime(req)
    assert exc.value.status_code == 422


def test_gstr3b_invalid_input_tax_credit_maps_to_422():
    req = Gstr3bRequest(lines=[_line()], input_tax_credit=float("inf"))
    with pytest.raises(HTTPException) as exc:
        gst_gstr3b(req)
    assert exc.value.status_code == 422
