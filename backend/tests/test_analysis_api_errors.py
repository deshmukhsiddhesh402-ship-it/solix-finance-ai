"""API regression tests for financial-analysis validation error mapping."""
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.analysis import (
    IrrRequest,
    NpvRequest,
    ScenarioAnalysisRequest,
    ScenarioIn,
    irr_endpoint,
    npv_endpoint,
    scenario_analysis_endpoint,
)


def test_npv_endpoint_maps_invalid_engine_input_to_http_422():
    with pytest.raises(HTTPException) as exc:
        npv_endpoint(NpvRequest(rate_pct=-100, cash_flows=[-100, 120]))

    assert exc.value.status_code == 422
    assert "greater than -100" in exc.value.detail


def test_irr_endpoint_maps_invalid_engine_input_to_http_422():
    with pytest.raises(HTTPException) as exc:
        irr_endpoint(IrrRequest(cash_flows=[]))

    assert exc.value.status_code == 422
    assert "non-empty list" in exc.value.detail


def test_scenario_endpoint_maps_invalid_engine_input_to_http_422():
    request = ScenarioAnalysisRequest(
        scenarios=[ScenarioIn(name=" ", revenue=100, cost=50, probability_pct=100)]
    )

    with pytest.raises(HTTPException) as exc:
        scenario_analysis_endpoint(request)

    assert exc.value.status_code == 422
    assert "Scenario name" in exc.value.detail


def test_valid_npv_and_irr_requests_keep_existing_response_shapes():
    assert npv_endpoint(NpvRequest(rate_pct=10, cash_flows=[-100, 110])) == {"npv": 0.0}
    result = irr_endpoint(IrrRequest(cash_flows=[-100, 110]))
    assert set(result) == {"irr_pct"}
    assert result["irr_pct"] == pytest.approx(10.0, abs=0.01)


def test_valid_scenario_request_keeps_existing_response_shape():
    result = scenario_analysis_endpoint(
        ScenarioAnalysisRequest(
            scenarios=[ScenarioIn(name="Base", revenue=100, cost=60, probability_pct=100)]
        )
    )

    assert result["expected_profit"] == 40
    assert result["best_case"] == "Base"
