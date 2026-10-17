import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.routers.analysis import (
    DcfRequest,
    IrrRequest,
    NpvRequest,
    ScenarioAnalysisRequest,
)


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (NpvRequest, {"rate_pct": 8, "cash_flows": []}),
        (NpvRequest, {"rate_pct": 8, "cash_flows": [0] * 501}),
        (IrrRequest, {"cash_flows": []}),
        (IrrRequest, {"cash_flows": [0] * 501}),
        (DcfRequest, {"projected_cash_flows": [], "discount_rate_pct": 10, "terminal_growth_rate_pct": 2}),
        (DcfRequest, {"projected_cash_flows": [0] * 101, "discount_rate_pct": 10, "terminal_growth_rate_pct": 2}),
        (ScenarioAnalysisRequest, {"scenarios": []}),
        (ScenarioAnalysisRequest, {"scenarios": [{"name": f"case-{i}", "revenue": 1, "cost": 1} for i in range(101)]}),
    ],
)
def test_analysis_requests_reject_empty_or_oversized_collections(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_analysis_requests_accept_collection_limits():
    assert len(NpvRequest.model_validate({"rate_pct": 8, "cash_flows": [0] * 500}).cash_flows) == 500
    assert len(IrrRequest.model_validate({"cash_flows": [0] * 500}).cash_flows) == 500
    assert len(
        DcfRequest.model_validate(
            {"projected_cash_flows": [0] * 100, "discount_rate_pct": 10, "terminal_growth_rate_pct": 2}
        ).projected_cash_flows
    ) == 100
    assert len(
        ScenarioAnalysisRequest.model_validate(
            {"scenarios": [{"name": f"case-{i}", "revenue": 1, "cost": 1} for i in range(100)]}
        ).scenarios
    ) == 100
