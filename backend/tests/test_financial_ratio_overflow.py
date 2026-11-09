"""Regression tests for finite financial-ratio outputs and API errors."""
from pathlib import Path
import math
import sys

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.accounting import RatiosRequest, ratios
from app.services.accounting_engine import financial_ratios


def _valid_values():
    return {
        "current_assets": 200.0,
        "current_liabilities": 100.0,
        "inventory": 20.0,
        "total_debt": 50.0,
        "total_equity": 200.0,
        "net_profit": 30.0,
        "revenue": 300.0,
        "total_assets": 500.0,
    }


@pytest.mark.parametrize(
    ("overrides", "label"),
    [
        ({"current_assets": 1e308, "current_liabilities": 1e-308}, "Current ratio"),
        ({"net_profit": 1e308, "revenue": 1e-308}, "Net profit margin"),
        ({"net_profit": 1e308, "total_assets": 1e-308}, "Return on assets"),
    ],
)
def test_financial_ratios_reject_finite_inputs_that_overflow_output(overrides, label):
    values = {**_valid_values(), **overrides}

    with pytest.raises(ValueError, match=label):
        financial_ratios(**values)


def test_ratio_endpoint_maps_overflow_validation_to_http_422():
    request = RatiosRequest(
        **{
            **_valid_values(),
            "current_assets": 1e308,
            "current_liabilities": 1e-308,
        }
    )

    with pytest.raises(HTTPException) as exc:
        ratios(request)

    assert exc.value.status_code == 422
    assert "Current ratio" in exc.value.detail


def test_valid_ratio_results_remain_finite_and_preserve_zero_denominator_behavior():
    result = financial_ratios(**_valid_values())

    assert all(value is None or math.isfinite(value) for value in result.values())
    assert result["current_ratio"] == 2.0
    assert result["quick_ratio"] == 1.8
    assert result["debt_to_equity"] == 0.25

    zero_denominators = financial_ratios(
        **{**_valid_values(), "current_liabilities": 0, "total_equity": 0, "revenue": 0, "total_assets": 0}
    )
    assert zero_denominators["current_ratio"] is None
    assert zero_denominators["quick_ratio"] is None
    assert zero_denominators["debt_to_equity"] is None
    assert zero_denominators["net_profit_margin_pct"] is None
    assert zero_denominators["return_on_assets_pct"] is None
    assert zero_denominators["return_on_equity_pct"] is None


@pytest.mark.parametrize(
    "field",
    [
        "current_assets",
        "current_liabilities",
        "inventory",
        "total_debt",
        "total_equity",
        "net_profit",
        "revenue",
        "total_assets",
    ],
)
@pytest.mark.parametrize("value", [True, False])
def test_ratio_request_rejects_boolean_values_before_float_coercion(field, value):
    values = _valid_values()
    values[field] = value

    with pytest.raises(ValidationError, match="numeric, not boolean"):
        RatiosRequest(**values)


def test_ratio_request_continues_to_accept_integer_financial_amounts():
    values = _valid_values()
    values["current_assets"] = 200

    request = RatiosRequest(**values)

    assert request.current_assets == 200.0
