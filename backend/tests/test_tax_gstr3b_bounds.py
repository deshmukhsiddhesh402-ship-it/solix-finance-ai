import pytest

from app.services.tax_engine import (
    GstInvoiceLine,
    MAX_GSTR3B_LINES,
    calculate_gst,
    gstr3b_summary,
)


def test_gstr3b_summary_preserves_normal_tax_and_credit_calculation():
    result = gstr3b_summary(
        [
            GstInvoiceLine(10_000.0, 18.0, False),
            GstInvoiceLine(5_000.0, 5.0, True),
        ],
        input_tax_credit=500.0,
    )

    assert result == {
        "total_taxable_value": 15_000.0,
        "total_output_tax": 2_050.0,
        "input_tax_credit_claimed": 500.0,
        "net_gst_payable": 1_550.0,
    }


def test_gstr3b_rejects_more_than_the_configured_line_limit():
    lines = [GstInvoiceLine(1.0, 0.0, True)] * (MAX_GSTR3B_LINES + 1)

    with pytest.raises(ValueError, match="cannot contain more than"):
        gstr3b_summary(lines)


def test_gstr3b_rejects_non_list_input():
    with pytest.raises(ValueError, match="lines must be a list"):
        gstr3b_summary(())  # type: ignore[arg-type]


def test_gstr3b_rejects_invalid_line_objects():
    with pytest.raises(ValueError, match="Each line must be a GstInvoiceLine"):
        gstr3b_summary([{"taxable_value": 100.0, "gst_rate_pct": 18.0, "is_interstate": True}])  # type: ignore[list-item]


def test_gstr3b_rejects_total_taxable_value_overflow():
    lines = [
        GstInvoiceLine(1e308, 0.0, True),
        GstInvoiceLine(1e308, 0.0, True),
    ]

    with pytest.raises(ValueError, match="supported numeric range"):
        gstr3b_summary(lines)


def test_gstr3b_rejects_invoice_total_overflow_before_returning_infinity():
    with pytest.raises(ValueError, match="supported numeric range"):
        calculate_gst(1e308, 100.0, True)


def test_gstr3b_rejects_non_finite_line_inputs():
    with pytest.raises(ValueError, match="taxable_value"):
        gstr3b_summary([GstInvoiceLine(float("inf"), 18.0, True)])


def test_gstr3b_allows_itc_above_output_tax_without_negative_payable():
    result = gstr3b_summary(
        [GstInvoiceLine(1_000.0, 5.0, True)],
        input_tax_credit=1_000.0,
    )

    assert result["net_gst_payable"] == 0.0
