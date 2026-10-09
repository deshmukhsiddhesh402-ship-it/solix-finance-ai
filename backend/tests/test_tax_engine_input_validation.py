import pytest

from app.services.tax_engine import (
    GstInvoiceLine,
    calculate_gst,
    calculate_income_tax_new_regime,
    calculate_tds,
    gstr3b_summary,
)


@pytest.mark.parametrize("value", [True, False, "100", None, float("nan"), float("inf"), -1])
def test_gst_rejects_invalid_taxable_values(value):
    with pytest.raises(ValueError):
        calculate_gst(value, 18, True)


@pytest.mark.parametrize("value", [True, "18", None, float("nan"), float("inf"), -0.1, 100.1])
def test_gst_rejects_invalid_rates(value):
    with pytest.raises(ValueError):
        calculate_gst(100, value, True)


@pytest.mark.parametrize("value", [1, 0, "false", None, [], {}])
def test_gst_requires_boolean_interstate_flag(value):
    with pytest.raises(ValueError):
        calculate_gst(100, 18, value)


@pytest.mark.parametrize("section", ["", " ", None, 194, [], {}])
def test_tds_rejects_invalid_section_types(section):
    with pytest.raises(ValueError):
        calculate_tds(1000, section)


@pytest.mark.parametrize("has_pan", [0, 1, "false", None, []])
def test_tds_requires_boolean_pan_flag(has_pan):
    with pytest.raises(ValueError):
        calculate_tds(1000, "194J", has_pan)


@pytest.mark.parametrize("lines", [None, {}, (), "invalid", [object()], [dict(taxable_value=100)]])
def test_gstr3b_rejects_invalid_line_collections(lines):
    with pytest.raises(ValueError):
        gstr3b_summary(lines)


@pytest.mark.parametrize("value", [True, "100", None, float("nan"), float("inf"), -1])
def test_income_tax_rejects_invalid_gross_salary(value):
    with pytest.raises(ValueError):
        calculate_income_tax_new_regime(value)


@pytest.mark.parametrize("value", [True, "100", None, float("nan"), float("inf"), -1])
def test_income_tax_rejects_invalid_other_income(value):
    with pytest.raises(ValueError):
        calculate_income_tax_new_regime(100_000, value)


def test_valid_tax_calculations_remain_supported():
    gst = calculate_gst(1000, 18, True)
    assert gst["total_tax"] == 180.0
    assert calculate_tds(10_000, "194J")["tds_amount"] == 1000.0
    summary = gstr3b_summary([GstInvoiceLine(1000, 18, True)])
    assert summary["total_output_tax"] == 180.0
    assert calculate_income_tax_new_regime(500_000)["total_tax_payable"] == 0.0
