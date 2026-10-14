"""Regression tests for Excel export of untrusted invoice OCR fields."""
import io

import pandas as pd
import pytest
from app.services.invoice_ocr_engine import invoices_to_excel


@pytest.mark.parametrize("gstin", [123, [], {}, True, ["not", "a", "GSTIN"]])
def test_excel_export_handles_malformed_gstin_types(gstin):
    output = invoices_to_excel([{"vendor_name": "Supplier", "vendor_gstin": gstin}])
    frame = pd.read_excel(io.BytesIO(output))

    assert frame.loc[0, "GSTIN Valid"] in (False, 0)
    assert pd.isna(frame.loc[0, "Vendor GSTIN"])


def test_excel_export_handles_malformed_line_items_and_non_finite_numbers():
    output = invoices_to_excel([{
        "vendor_name": {"unexpected": "object"},
        "line_items": {"not": "a list"},
        "taxable_value": float("inf"),
        "total_amount": float("nan"),
    }])
    frame = pd.read_excel(io.BytesIO(output))

    assert frame.loc[0, "Line Items"] == 0
    assert pd.isna(frame.loc[0, "Vendor Name"])
    assert pd.isna(frame.loc[0, "Taxable Value"])
    assert pd.isna(frame.loc[0, "Total Amount"])


def test_excel_export_truncates_oversized_text_to_excel_cell_limit():
    output = invoices_to_excel([{"vendor_name": "x" * 40000}])
    frame = pd.read_excel(io.BytesIO(output))

    assert len(frame.loc[0, "Vendor Name"]) == 32767
