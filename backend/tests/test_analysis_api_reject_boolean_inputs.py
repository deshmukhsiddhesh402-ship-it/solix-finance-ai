"""Request-boundary regression tests for boolean analysis inputs."""
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.analysis import (
    BreakEvenRequest,
    CagrRequest,
    DcfRequest,
    IrrRequest,
    NpvRequest,
    ScenarioIn,
)


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (NpvRequest, {"rate_pct": 10, "cash_flows": [-100, 110]}, "rate_pct"),
        (CagrRequest, {"beginning_value": 100, "ending_value": 121, "years": 2}, "beginning_value"),
        (CagrRequest, {"beginning_value": 100, "ending_value": 121, "years": 2}, "ending_value"),
        (CagrRequest, {"beginning_value": 100, "ending_value": 121, "years": 2}, "years"),
        (BreakEvenRequest, {"fixed_costs": 100, "price_per_unit": 10, "variable_cost_per_unit": 5}, "fixed_costs"),
        (BreakEvenRequest, {"fixed_costs": 100, "price_per_unit": 10, "variable_cost_per_unit": 5}, "price_per_unit"),
        (BreakEvenRequest, {"fixed_costs": 100, "price_per_unit": 10, "variable_cost_per_unit": 5}, "variable_cost_per_unit"),
        (DcfRequest, {"projected_cash_flows": [100, 110], "discount_rate_pct": 10, "terminal_growth_rate_pct": 2}, "discount_rate_pct"),
        (DcfRequest, {"projected_cash_flows": [100, 110], "discount_rate_pct": 10, "terminal_growth_rate_pct": 2}, "terminal_growth_rate_pct"),
        (ScenarioIn, {"name": "Base", "revenue": 100, "cost": 60, "probability_pct": 100}, "revenue"),
        (ScenarioIn, {"name": "Base", "revenue": 100, "cost": 60, "probability_pct": 100}, "cost"),
        (ScenarioIn, {"name": "Base", "revenue": 100, "cost": 60, "probability_pct": 100}, "probability_pct"),
    ],
)
@pytest.mark.parametrize("value", [True, False])
def test_analysis_request_models_reject_boolean_scalar_inputs(model, payload, field, value):
    invalid = {**payload, field: value}

    with pytest.raises(ValidationError, match="numeric, not boolean"):
        model(**invalid)


@pytest.mark.parametrize("model,payload,field", [
    (NpvRequest, {"rate_pct": 10, "cash_flows": [-100, 110]}, "cash_flows"),
    (IrrRequest, {"cash_flows": [-100, 110]}, "cash_flows"),
    (DcfRequest, {"projected_cash_flows": [100, 110], "discount_rate_pct": 10, "terminal_growth_rate_pct": 2}, "projected_cash_flows"),
])
@pytest.mark.parametrize("value", [True, False])
def test_analysis_request_models_reject_boolean_cash_flow_elements(model, payload, field, value):
    items = list(payload[field])
    items[0] = value

    with pytest.raises(ValidationError, match=r"must be numeric, not boolean"):
        model(**{**payload, field: items})


def test_analysis_request_models_continue_accepting_integer_values():
    npv = NpvRequest(rate_pct=10, cash_flows=[-100, 110])
    irr = IrrRequest(cash_flows=[-100, 110])
    cagr = CagrRequest(beginning_value=100, ending_value=121, years=2)
    scenario = ScenarioIn(name="Base", revenue=100, cost=60, probability_pct=100)

    assert npv.rate_pct == 10.0
    assert irr.cash_flows == [-100.0, 110.0]
    assert cagr.years == 2.0
    assert scenario.revenue == 100.0
