"""Regression tests for strict numeric checks in direct accounting-engine calls."""
import sys
from pathlib import Path

# CI workflows invoke pytest from different working directories.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.services.accounting_engine import (
    InventoryTxn,
    financial_ratios,
    inventory_valuation,
    straight_line_depreciation,
    wdv_depreciation_schedule,
)


@pytest.mark.parametrize("field", [
    "current_assets", "current_liabilities", "inventory", "total_debt",
    "total_equity", "net_profit", "revenue", "total_assets",
])
@pytest.mark.parametrize("bad_value", [True, 10**10000], ids=["bool", "huge-int"])
def test_financial_ratios_reject_boolean_and_overflowing_values(field, bad_value):
    values = {
        "current_assets": 100,
        "current_liabilities": 50,
        "inventory": 10,
        "total_debt": 20,
        "total_equity": 80,
        "net_profit": 15,
        "revenue": 200,
        "total_assets": 150,
    }
    values[field] = bad_value
    with pytest.raises(ValueError):
        financial_ratios(**values)


@pytest.mark.parametrize("field", ["cost", "salvage"])
@pytest.mark.parametrize("bad_value", [True, 10**10000], ids=["bool", "huge-int"])
def test_straight_line_depreciation_rejects_boolean_and_overflowing_amounts(field, bad_value):
    values = {"cost": 1000, "salvage": 100}
    values[field] = bad_value
    with pytest.raises(ValueError):
        straight_line_depreciation(**values, useful_life_years=5)


@pytest.mark.parametrize("years", [True, 1.5], ids=["bool", "fractional"])
def test_straight_line_depreciation_requires_integer_useful_life(years):
    with pytest.raises(ValueError):
        straight_line_depreciation(1000, 100, years)


@pytest.mark.parametrize("field", ["cost", "rate_pct"])
@pytest.mark.parametrize("bad_value", [True, 10**10000], ids=["bool", "huge-int"])
def test_wdv_depreciation_rejects_boolean_and_overflowing_inputs(field, bad_value):
    values = {"cost": 1000, "rate_pct": 15}
    values[field] = bad_value
    with pytest.raises(ValueError):
        wdv_depreciation_schedule(**values, years=5)


@pytest.mark.parametrize("field", ["quantity", "unit_cost"])
@pytest.mark.parametrize("bad_value", [True, 10**10000], ids=["bool", "huge-int"])
def test_inventory_valuation_rejects_boolean_and_overflowing_inputs(field, bad_value):
    values = {"quantity": 10, "unit_cost": 12}
    values[field] = bad_value
    txns = [InventoryTxn(txn_type="purchase", **values)]
    with pytest.raises(ValueError):
        inventory_valuation(txns, "FIFO")


def test_valid_direct_engine_calculations_remain_supported():
    assert straight_line_depreciation(1000, 100, 5) == 180.0
    assert len(wdv_depreciation_schedule(1000, 15, 5)) == 5
    result = inventory_valuation(
        [InventoryTxn("purchase", 10, 12), InventoryTxn("sale", 2, 12)],
        "FIFO",
    )
    assert result["closing_quantity"] == 8
    assert result["closing_inventory_value"] == 96.0
