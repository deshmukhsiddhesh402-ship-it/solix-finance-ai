"""Regression tests for GSTR-3B summary validation."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.tax_engine import GstInvoiceLine, gstr3b_summary


def test_gstr3b_summary_rejects_non_invoice_line_objects():
    with pytest.raises(ValueError, match="GstInvoiceLine"):
        gstr3b_summary([None])


def test_gstr3b_summary_rejects_non_finite_aggregate():
    lines = [
        GstInvoiceLine(taxable_value=8e307, gst_rate_pct=0, is_interstate=True),
        GstInvoiceLine(taxable_value=8e307, gst_rate_pct=0, is_interstate=True),
    ]

    with pytest.raises(ValueError, match="numeric range"):
        gstr3b_summary(lines)


def test_gstr3b_summary_keeps_valid_totals():
    lines = [
        GstInvoiceLine(taxable_value=1000, gst_rate_pct=18, is_interstate=True),
        GstInvoiceLine(taxable_value=500, gst_rate_pct=5, is_interstate=False),
    ]

    result = gstr3b_summary(lines, input_tax_credit=50)

    assert result["total_taxable_value"] == 1500
    assert result["total_output_tax"] == 205
    assert result["input_tax_credit_claimed"] == 50
    assert result["net_gst_payable"] == 155
