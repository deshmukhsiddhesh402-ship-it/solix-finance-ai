import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

"""Direct accounting-engine numeric type validation regression tests."""
import pytest

from app.services.accounting_engine import (
    InventoryTxn,
    LedgerLine,
    build_trial_balance,
    financial_ratios,
    inventory_valuation,
    straight_line_depreciation,
    wdv_depreciation_schedule,
)


@pytest.mark.parametrize("debit,credit", [(True, 0.0), (0.0, False), ("1", 0.0)])
def test_trial_balance_rejects_boolean_and_non_numeric_amounts(debit, credit):
    with pytest.raises(ValueError, match="finite number"):
        build_trial_balance([LedgerLine("Cash", "asset", debit=debit, credit=credit)])


def test_financial_ratios_reject_boolean_balance_inputs():
    with pytest.raises(ValueError, match="current_assets"):
        financial_ratios(True, 1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 1.0)


@pytest.mark.parametrize("useful_life", [True, False, 1.5, "5"])
def test_straight_line_depreciation_requires_positive_integer_life(useful_life):
    with pytest.raises(ValueError, match="positive integer"):
        straight_line_depreciation(100.0, 0.0, useful_life)


@pytest.mark.parametrize("cost,rate", [(True, 10.0), (100.0, False), ("100", 10.0)])
def test_wdv_depreciation_rejects_boolean_and_non_numeric_inputs(cost, rate):
    with pytest.raises(ValueError, match="finite number"):
        wdv_depreciation_schedule(cost, rate, 3)


@pytest.mark.parametrize(
    "quantity,unit_cost",
    [(True, 10.0), (1.0, False), ("1", 10.0)],
)
def test_inventory_valuation_rejects_boolean_and_non_numeric_values(quantity, unit_cost):
    with pytest.raises(ValueError, match="finite number"):
        inventory_valuation([InventoryTxn("purchase", quantity, unit_cost)], "FIFO")
