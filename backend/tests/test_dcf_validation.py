import math

import pytest

from app.services.analysis_engine import dcf_valuation


def test_dcf_returns_finite_values_for_a_valid_forecast():
    result = dcf_valuation([100.0, 110.0, 120.0], 10.0, 2.0)

    assert set(result) == {
        "pv_of_forecast_cash_flows",
        "terminal_value",
        "pv_of_terminal_value",
        "enterprise_value",
    }
    assert all(math.isfinite(value) for value in result.values())


@pytest.mark.parametrize("cash_flows", [[], (), None])
def test_dcf_requires_a_non_empty_list_of_forecast_cash_flows(cash_flows):
    with pytest.raises(ValueError, match="non-empty list"):
        dcf_valuation(cash_flows, 10.0, 2.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "cash_flows",
    [
        [float("nan")],
        [float("inf")],
        [True],
        ["100"],
    ],
)
def test_dcf_rejects_invalid_forecast_cash_flows(cash_flows):
    with pytest.raises(ValueError, match=r"projected_cash_flows\[0\] must be a finite number"):
        dcf_valuation(cash_flows, 10.0, 2.0)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("discount_rate", "growth_rate"),
    [
        (float("nan"), 2.0),
        (10.0, float("inf")),
        (-100.0, -101.0),
        (2.0, 2.0),
    ],
)
def test_dcf_rejects_invalid_discount_and_growth_rates(discount_rate, growth_rate):
    with pytest.raises(ValueError):
        dcf_valuation([100.0, 110.0], discount_rate, growth_rate)


def test_dcf_rejects_forecasts_longer_than_100_periods():
    with pytest.raises(ValueError, match="more than 100 periods"):
        dcf_valuation([1.0] * 101, 10.0, 2.0)


def test_dcf_rejects_numeric_overflow_in_terminal_value():
    with pytest.raises(ValueError, match="supported numeric range"):
        dcf_valuation([1e308], 10.0, 2.0)
