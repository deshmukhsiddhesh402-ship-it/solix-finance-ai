"""
Run with: pytest backend/tests -v
These test the pure calculation engines directly (no API/DB needed).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decimal import Decimal
import pytest

from app.services.accounting_engine import (
    LedgerLine, build_trial_balance, build_profit_and_loss, build_balance_sheet,
    straight_line_depreciation, wdv_depreciation_schedule, InventoryTxn, inventory_valuation,
)
from app.services.tax_engine import (
    GstInvoiceLine, calculate_gst, calculate_tds, gstr3b_summary,
    calculate_income_tax_new_regime,
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


def test_depreciation_uses_decimal_half_up_currency_rounding():
    # 100.05 / 2 = 50.025; monetary output must round half-up to ₹50.03.
    assert straight_line_depreciation(cost=100.05, salvage=0, useful_life_years=2) == 50.03
    # ₹0.05 × 10% = ₹0.005; WDV depreciation rounds half-up to ₹0.01.
    schedule = wdv_depreciation_schedule(cost=0.05, rate_pct=10, years=1)
    assert schedule == [{"year": 1, "depreciation": 0.01, "closing_wdv": 0.04}]


def test_straight_line_depreciation_rejects_boolean_useful_life():
    with pytest.raises(ValueError, match="positive integer"):
        straight_line_depreciation(cost=100, salvage=0, useful_life_years=True)


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



def test_inventory_valuation_uses_decimal_half_up_currency_rounding():
    fifo = inventory_valuation(
        [InventoryTxn("purchase", 1, 2.675), InventoryTxn("sale", 1, 0)],
        "FIFO",
    )
    assert fifo["cogs"] == 2.68
    assert fifo["closing_inventory_value"] == 0.0

    weighted_average = inventory_valuation(
        [
            InventoryTxn("purchase", 1, 1.005),
            InventoryTxn("purchase", 1, 1.015),
            InventoryTxn("sale", 1, 0),
        ],
        "WAVG",
    )
    assert weighted_average["cogs"] == 1.01
    assert weighted_average["closing_inventory_value"] == 1.01


def test_inventory_valuation_rejects_boolean_and_string_numeric_inputs():
    with pytest.raises(ValueError, match="finite number"):
        inventory_valuation([InventoryTxn("purchase", True, 100)], "FIFO")
    with pytest.raises(ValueError, match="finite number"):
        inventory_valuation([InventoryTxn("purchase", "1", 100)], "FIFO")


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



def test_trial_balance_uses_decimal_half_up_rounding_for_currency():
    lines = [
        LedgerLine("Office Expense", "expense", debit=2.675),
        LedgerLine("Accounts Payable", "liability", credit=2.675),
    ]
    result = build_trial_balance(lines)
    assert result["rows"][0]["debit"] == 2.68
    assert result["rows"][1]["credit"] == 2.68
    assert result["total_debit"] == 2.68
    assert result["total_credit"] == 2.68
    assert result["is_balanced"] is True


def test_financial_statements_sum_currency_with_decimal_arithmetic():
    rows = [
        {"account": "Sales A", "type": "income", "debit": Decimal("0"), "credit": Decimal("0.10")},
        {"account": "Sales B", "type": "income", "debit": Decimal("0"), "credit": Decimal("0.20")},
        {"account": "Office Expense", "type": "expense", "debit": Decimal("0.10"), "credit": Decimal("0")},
        {"account": "Cash", "type": "asset", "debit": Decimal("0.20"), "credit": Decimal("0")},
        {"account": "Capital", "type": "equity", "debit": Decimal("0"), "credit": Decimal("0.20")},
    ]
    pnl = build_profit_and_loss(rows)
    assert pnl == {"total_income": 0.30, "total_expense": 0.10, "net_profit": 0.20}
    balance_sheet = build_balance_sheet(rows, Decimal("0"))
    assert balance_sheet["total_assets"] == 0.20
    assert balance_sheet["total_equity"] == 0.20
    assert balance_sheet["balances"] is True


def test_trial_balance_rejects_non_finite_decimal_amounts():
    with pytest.raises(ValueError, match="finite"):
        build_trial_balance([LedgerLine("Cash", "asset", debit=Decimal("NaN"))])



def test_gst_uses_decimal_half_up_rounding_and_reconciles_invoice_total():
    interstate = calculate_gst(2.675, 18, True)
    assert interstate["igst"] == 0.48
    assert interstate["invoice_total"] == 3.16

    intrastate = calculate_gst(2.675, 18, False)
    assert intrastate["cgst"] == 0.24
    assert intrastate["sgst"] == 0.24
    assert intrastate["total_tax"] == intrastate["cgst"] + intrastate["sgst"]
    assert intrastate["invoice_total"] == 3.16


def test_tds_uses_decimal_half_up_rounding_for_tax_and_net_payment():
    result = calculate_tds(2.675, "194J")
    assert result["tds_amount"] == 0.27
    assert result["net_payment"] == 2.41


def test_gstr3b_summary_aggregates_tax_and_input_credit_safely():
    summary = gstr3b_summary(
        [
            GstInvoiceLine(taxable_value=2.675, gst_rate_pct=18, is_interstate=True),
            GstInvoiceLine(taxable_value=2.675, gst_rate_pct=18, is_interstate=True),
        ],
        input_tax_credit=0.20,
    )
    assert summary == {
        "total_taxable_value": 5.35,
        "total_output_tax": 0.96,
        "input_tax_credit_claimed": 0.20,
        "net_gst_payable": 0.76,
    }
