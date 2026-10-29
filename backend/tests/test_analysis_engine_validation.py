"""Regression tests for financial-analysis input validation."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.analysis_engine import (
    Scenario,
    break_even,
    cagr,
    dcf_valuation,
    irr,
    npv,
    scenario_analysis,
)


@pytest.mark.parametrize("rate", [float("nan"), float("inf"), -100, -101])
def test_npv_rejects_invalid_discount_rates(rate):
    with pytest.raises(ValueError):
        npv(rate, [-100, 120])


@pytest.mark.parametrize("cash_flows", [[], [float("nan")], [float("inf")]])
def test_npv_rejects_empty_or_non_finite_cash_flows(cash_flows):
    with pytest.raises(ValueError):
        npv(10, cash_flows)


def test_irr_rejects_invalid_bounds_and_cash_flows():
    with pytest.raises(ValueError):
        irr([-100, 120], low=-100)
    with pytest.raises(ValueError):
        irr([-100, float("nan")])
    with pytest.raises(ValueError):
        irr([-100, 120], max_iter=0)


@pytest.mark.parametrize(
    "values",
    [(0, 100, 1), (100, 0, 1), (100, 200, 0), (100, float("inf"), 1)],
)
def test_cagr_rejects_invalid_values(values):
    with pytest.raises(ValueError):
        cagr(*values)


@pytest.mark.parametrize("values", [(-1, 10, 2), (100, 0, 2), (100, 10, float("nan"))])
def test_break_even_rejects_invalid_values(values):
    with pytest.raises(ValueError):
        break_even(*values)


def test_dcf_rejects_empty_or_non_finite_forecasts_and_invalid_rates():
    with pytest.raises(ValueError):
        dcf_valuation([], 10, 2)
    with pytest.raises(ValueError):
        dcf_valuation([100, float("inf")], 10, 2)
    with pytest.raises(ValueError):
        dcf_valuation([100], float("nan"), 2)
    with pytest.raises(ValueError):
        dcf_valuation([100], 2, 2)


def test_scenario_analysis_rejects_non_finite_and_invalid_probability():
    with pytest.raises(ValueError):
        scenario_analysis([Scenario("Base", float("nan"), 10, 50)])
    with pytest.raises(ValueError):
        scenario_analysis([Scenario("Base", 100, 10, 101)])
    with pytest.raises(ValueError):
        scenario_analysis([Scenario(" ", 100, 10, 50)])


def test_valid_financial_analysis_examples_remain_supported():
    assert npv(10, [-1000, 1100]) == 0
    assert cagr(100, 121, 2) == 10
    assert break_even(1000, 100, 60)["break_even_units"] == 25
    assert dcf_valuation([100, 110], 10, 2)["enterprise_value"] > 0
    assert scenario_analysis([Scenario("Base", 100, 60, 100)])["expected_profit"] == 40
