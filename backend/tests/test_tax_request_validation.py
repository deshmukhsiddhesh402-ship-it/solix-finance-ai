"""Request-boundary tests for tax API numeric and list-size constraints."""
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.tax import GstRequest, Gstr3bRequest, IncomeTaxRequest, TdsRequest


@pytest.mark.parametrize("payload", [
    {"taxable_value": -1, "gst_rate_pct": 18, "is_interstate": True},
    {"taxable_value": float("inf"), "gst_rate_pct": 18, "is_interstate": True},
    {"taxable_value": 100, "gst_rate_pct": 101, "is_interstate": True},
])
def test_gst_request_rejects_invalid_amounts_and_rates(payload):
    with pytest.raises(ValidationError):
        GstRequest(**payload)


def test_gstr3b_request_bounds_line_count():
    with pytest.raises(ValidationError):
        Gstr3bRequest(lines=[
            {"taxable_value": 0, "gst_rate_pct": 0, "is_interstate": True}
            for _ in range(5001)
        ])


@pytest.mark.parametrize("payload", [
    {"gross_salary": -1},
    {"gross_salary": float("nan")},
    {"gross_salary": 1000, "other_income": float("inf")},
])
def test_income_tax_request_rejects_invalid_amounts(payload):
    with pytest.raises(ValidationError):
        IncomeTaxRequest(**payload)


def test_tds_request_rejects_non_finite_amount():
    with pytest.raises(ValidationError):
        TdsRequest(amount_paid=float("inf"), section="194C")
