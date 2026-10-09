import sys
from pathlib import Path

# CI workflows invoke pytest from different working directories.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.services.tax_engine import (
    calculate_gst,
    calculate_income_tax_new_regime,
    calculate_tds,
    gstr3b_summary,
)


@pytest.mark.parametrize("value", [True, False, 10**10000], ids=["true", "false", "huge-int"])
def test_gst_rejects_boolean_or_unrepresentably_large_amount(value):
    with pytest.raises(ValueError):
        calculate_gst(value, 18, True)


@pytest.mark.parametrize("value", [True, False, 10**10000], ids=["true", "false", "huge-int"])
def test_gst_rejects_boolean_or_unrepresentably_large_rate(value):
    with pytest.raises(ValueError):
        calculate_gst(100, value, True)


@pytest.mark.parametrize("value", [True, False, 10**10000], ids=["true", "false", "huge-int"])
def test_tds_rejects_boolean_or_unrepresentably_large_amount(value):
    with pytest.raises(ValueError):
        calculate_tds(value, "194J")


@pytest.mark.parametrize("value", [True, False, 10**10000], ids=["true", "false", "huge-int"])
def test_income_tax_rejects_boolean_or_unrepresentably_large_salary(value):
    with pytest.raises(ValueError):
        calculate_income_tax_new_regime(value)


@pytest.mark.parametrize("value", [True, False, 10**10000], ids=["true", "false", "huge-int"])
def test_income_tax_rejects_boolean_or_unrepresentably_large_other_income(value):
    with pytest.raises(ValueError):
        calculate_income_tax_new_regime(100_000, value)


@pytest.mark.parametrize("value", [True, False, 10**10000], ids=["true", "false", "huge-int"])
def test_gstr3b_rejects_boolean_or_unrepresentably_large_input_credit(value):
    with pytest.raises(ValueError):
        gstr3b_summary([], input_tax_credit=value)


def test_valid_tax_calculations_remain_supported():
    assert calculate_gst(1000, 18, True)["total_tax"] == 180.0
    assert calculate_tds(10_000, "194J")["tds_amount"] == 1000.0
    assert calculate_income_tax_new_regime(500_000)["total_tax_payable"] == 0.0
