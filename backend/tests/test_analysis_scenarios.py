import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.analysis_engine import Scenario, scenario_analysis


def test_scenario_analysis_expected_profit_normalizes_probabilities():
    result = scenario_analysis([
        Scenario("base", 1000, 600, 60),
        Scenario("downside", 700, 600, 40),
    ])
    assert result["expected_profit"] == 260.0
    assert result["best_case"] == "base"
    assert result["worst_case"] == "downside"


def test_scenario_analysis_empty_list_keeps_empty_result_contract():
    result = scenario_analysis([])
    assert result == {
        "scenarios": [],
        "expected_profit": None,
        "best_case": None,
        "worst_case": None,
    }


@pytest.mark.parametrize("probability", [-0.1, 100.1, float("nan"), float("inf"), True, "25"])
def test_scenario_analysis_rejects_invalid_probabilities(probability):
    with pytest.raises(ValueError):
        scenario_analysis([Scenario("base", 100, 60, probability)])


@pytest.mark.parametrize("revenue,cost", [
    (float("nan"), 1),
    (1, float("inf")),
    (True, 1),
    ("100", 1),
])
def test_scenario_analysis_rejects_invalid_revenue_and_cost(revenue, cost):
    with pytest.raises(ValueError):
        scenario_analysis([Scenario("base", revenue, cost, 50)])


def test_scenario_analysis_rejects_invalid_container_and_rows():
    with pytest.raises(ValueError, match="must be a list"):
        scenario_analysis(None)
    with pytest.raises(ValueError, match="Scenario object"):
        scenario_analysis([{"name": "base", "revenue": 100, "cost": 60}])


def test_scenario_analysis_rejects_blank_name():
    with pytest.raises(ValueError, match="non-empty string"):
        scenario_analysis([Scenario("  ", 100, 60, 100)])


def test_scenario_analysis_handles_zero_probability_without_expected_profit():
    result = scenario_analysis([Scenario("base", 100, 60, 0)])
    assert result["expected_profit"] is None
    assert result["scenarios"][0]["profit"] == 40
