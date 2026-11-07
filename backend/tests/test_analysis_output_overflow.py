"""Regression tests for finite NPV, CAGR, and break-even outputs."""
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.analysis import NpvRequest, npv_endpoint
from app.services.analysis_engine import break_even, cagr, npv


def test_npv_rejects_discount_factor_underflow():
    with pytest.raises(ValueError, match="NPV calculation exceeds"):
        npv(-99.9999, [1.0] * 500)


def test_cagr_rejects_overflowing_growth_multiple():
    with pytest.raises(ValueError, match="CAGR result exceeds"):
        cagr(1e-308, 1e308, 1)


def test_break_even_rejects_overflowing_units_and_revenue():
    with pytest.raises(ValueError, match="Break-even units exceeds"):
        break_even(1e308, 1.0, 0.9999999999999999)


def test_npv_endpoint_maps_numeric_overflow_to_http_422():
    request = NpvRequest(rate_pct=-99.9999, cash_flows=[1.0] * 500)

    with pytest.raises(HTTPException) as exc:
        npv_endpoint(request)

    assert exc.value.status_code == 422
    assert "NPV calculation exceeds" in exc.value.detail


def test_normal_financial_analysis_results_remain_unchanged():
    assert npv(10, [-1000, 1100]) == 0.0
    assert cagr(100, 121, 2) == 10.0
    assert break_even(50_000, 100, 60)["break_even_units"] == 1250.0
