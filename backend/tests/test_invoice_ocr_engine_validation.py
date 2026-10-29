"""Regression tests for malformed OCR invoice amount data."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.invoice_ocr_engine import invoice_to_journal_lines


@pytest.mark.parametrize("invoice", [
    {"taxable_value": [], "total_amount": 0},
    {"taxable_value": 100, "cgst_amount": {}, "total_amount": 100},
    None,
])
def test_invoice_journal_conversion_rejects_malformed_amount_data(invoice):
    with pytest.raises(ValueError):
        invoice_to_journal_lines(invoice)
