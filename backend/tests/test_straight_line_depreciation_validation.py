"""Regression tests for strict straight-line depreciation input validation."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.accounting_engine import straight_line_depreciation


def test_straight_line_depreciation_accepts_valid_inputs():
    assert straight_line_depreciation(cost=110000, salvage=10000, useful_life_years=10) == 10000.0


@pytest.mark.parametrize("years", [True, False, 0, -1, 1.5, "5", None])
def test_straight_line_depreciation_rejects_non_positive_or_non_integer_life(years):
    with pytest.raises(ValueError, match="positive integer"):
        straight_line_depreciation(cost=100, salvage=0, useful_life_years=years)


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), float("-inf"), "100", None])
def test_straight_line_depreciation_rejects_invalid_cost_and_salvage(value):
    with pytest.raises(ValueError, match="finite numbers"):
        straight_line_depreciation(cost=value, salvage=0, useful_life_years=5)
    with pytest.raises(ValueError, match="finite numbers"):
        straight_line_depreciation(cost=100, salvage=value, useful_life_years=5)


@pytest.mark.parametrize(
    "cost,salvage",
    [(-1, 0), (100, -1), (100, 101)],
)
def test_straight_line_depreciation_rejects_invalid_asset_values(cost, salvage):
    with pytest.raises(ValueError):
        straight_line_depreciation(cost=cost, salvage=salvage, useful_life_years=5)
