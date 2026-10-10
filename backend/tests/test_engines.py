"""
Run with: pytest backend/tests -v
These test the pure calculation engines directly (no API/DB needed).
"""
import sys, os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.accounting_engine import (
    LedgerLine, build_trial_balance, straight_line_depreciation,
    wdv_depreciation_schedule, InventoryTxn, inventory_valuation,
)
from app.services.tax_engine import (
    calculate_gst, calculate_tds, calculate_income_tax_new_regime,
)
from app.services.analysis_engine import npv, irr, cagr, break_even, dcf_valuation


def test_trial_balance_balances():
    lines = [
        LedgerLine("Cash", "asset", debit=100000),
        LedgerLine("Capital", "equity", credit=100000),
        LedgerLine("Rent Expense", "expense", debit=20000),
        LedgerLine("Cash", "asset", credit=20000),
    ]
    tb = build_trial_balance(lines)
    assert tb["is_balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]


def test_straight_line_depreciation():
    assert straight_line_depreciation(cost=110000, salvage=10000, useful_life_years=10) == 10000.0


def test_wdv_schedule_decreases():
    schedule = wdv_depreciation_schedule(cost=100000, rate_pct=20, years=3)
    assert schedule[0]["closing_wdv"] > schedule[1]["closing_wdv"] > schedule[2]["closing_wdv"]


def test_fifo_inventory_valuation():
    txns = [
        InventoryTxn("purchase", 10, 100),
        InventoryTxn("purchase", 10, 120),
        InventoryTxn("sale", 12),
    ]
    result = inventory_valuation(txns, "FIFO")
    # FIFO sells the 10 units @100 first, then 2 units @120 => COGS = 1000 + 240 = 1240
    assert result["cogs"] == 1240.0
    assert result["closing_quantity"] == 8


def test_gst_intrastate_split():
    result = calculate_gst(taxable_value=10000, gst_rate_pct=18, is_interstate=False)
    assert result["cgst"] == 900.0
    assert result["sgst"] == 900.0
    assert result["igst"] == 0.0


def test_tds_no_pan_flat_20pct():
    result = calculate_tds(amount_paid=100000, section="194J", has_pan=False)
    assert result["rate_applied_pct"] == 20.0
    assert result["tds_amount"] == 20000.0


def test_income_tax_87a_rebate_applies_at_12L():
    result = calculate_income_tax_new_regime(gross_salary=1_200_000)
    # after 75k standard deduction, taxable = 1,125,000 <= 12,00,000 -> rebate wipes tax
    assert result["total_tax_payable"] == 0.0


def test_income_tax_above_rebate_threshold():
    result = calculate_income_tax_new_regime(gross_salary=2_000_000)
    assert result["total_tax_payable"] > 0


def test_npv_classic_textbook_example():
    # -1000 outlay, 300/yr for 5 years @10% -> known answer ~137.24
    result = npv(10, [-1000, 300, 300, 300, 300, 300])
    assert abs(result - 137.24) < 0.5


def test_irr_matches_npv_zero_crossing():
    cf = [-1000, 300, 300, 300, 300, 300]
    rate = irr(cf)
    assert abs(npv(rate, cf)) < 1.0  # NPV at the found IRR should be ~0


def test_cagr_doubling_in_5_years():
    assert abs(cagr(100000, 200000, 5) - 14.87) < 0.05


def test_break_even_units():
    result = break_even(fixed_costs=50000, price_per_unit=100, variable_cost_per_unit=60)
    assert result["break_even_units"] == 1250.0


def test_dcf_enterprise_value_positive():
    result = dcf_valuation([100, 110, 121], discount_rate_pct=10, terminal_growth_rate_pct=3)
    assert result["enterprise_value"] > 0


@pytest.mark.parametrize("rate,flows", [
    (float("nan"), [-100, 150]),
    (float("inf"), [-100, 150]),
    (10, [-100, float("nan")]),
    (10, [-100, float("inf")]),
    (True, [-100, 150]),
    (10, [-100, True]),
])
def test_npv_rejects_invalid_numeric_inputs(rate, flows):
    with pytest.raises(ValueError, match="finite number"):
        npv(rate, flows)


def test_npv_rejects_rate_at_or_below_negative_100_percent():
    with pytest.raises(ValueError, match="greater than -100"):
        npv(-100, [-100, 150])


def test_irr_rejects_invalid_bounds_and_iteration_count():
    with pytest.raises(ValueError, match="bounds"):
        irr([-100, 150], low=-100)
    with pytest.raises(ValueError, match="positive integer"):
        irr([-100, 150], max_iter=True)


@pytest.mark.parametrize("beginning,ending,years", [
    (0, 100, 1),
    (100, 0, 1),
    (100, -1, 1),
    (100, 200, float("inf")),
    (True, 200, 1),
])
def test_cagr_rejects_invalid_inputs(beginning, ending, years):
    with pytest.raises(ValueError):
        cagr(beginning, ending, years)


def test_break_even_rejects_negative_costs_and_non_finite_values():
    with pytest.raises(ValueError):
        break_even(-1, 100, 60)
    with pytest.raises(ValueError, match="finite number"):
        break_even(100, float("nan"), 60)


def test_dcf_rejects_empty_or_non_finite_cash_flows():
    with pytest.raises(ValueError, match="non-empty list"):
        dcf_valuation([], discount_rate_pct=10, terminal_growth_rate_pct=3)
    with pytest.raises(ValueError, match="finite number"):
        dcf_valuation([100, float("inf")], discount_rate_pct=10, terminal_growth_rate_pct=3)
