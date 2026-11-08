"""Regression tests for formula injection in OCR-generated workbooks."""

from io import BytesIO

from openpyxl import load_workbook

from app.services.invoice_ocr_engine import invoices_to_excel


def test_invoice_export_escapes_formula_like_text_without_mutating_source():
    invoice = {
        "vendor_name": " =HYPERLINK(\"https://evil.example\",\"open\")",
        "vendor_gstin": "=1+1",
        "invoice_number": "@SUM(A1:A2)",
        "invoice_date": "\t=cmd|' /C calc'!A0",
        "taxable_value": "-1+2",
        "cgst_amount": 0,
        "sgst_amount": 0,
        "igst_amount": 0,
        "total_amount": 0,
        "line_items": [],
    }

    workbook_bytes = invoices_to_excel([invoice])
    worksheet = load_workbook(BytesIO(workbook_bytes), data_only=False)["Invoices"]

    expected = {
        "A2": "' =HYPERLINK(\"https://evil.example\",\"open\")",
        "B2": "'=1+1",
        "D2": "'@SUM(A1:A2)",
        "E2": "'\t=cmd|' /C calc'!A0",
        "F2": "'-1+2",
    }
    for cell, value in expected.items():
        assert worksheet[cell].value == value
        assert worksheet[cell].data_type != "f"

    assert invoice["vendor_name"].startswith(" ")
    assert invoice["vendor_gstin"] == "=1+1"


def test_invoice_export_preserves_numeric_values_and_ordinary_text():
    workbook_bytes = invoices_to_excel(
        [{
            "vendor_name": "Sample Vendor",
            "vendor_gstin": "27ABCDE1234F1Z5",
            "invoice_number": "INV-100",
            "taxable_value": 1000,
            "cgst_amount": 90,
            "sgst_amount": 90,
            "igst_amount": 0,
            "total_amount": 1180,
            "line_items": [],
        }]
    )
    worksheet = load_workbook(BytesIO(workbook_bytes), data_only=False)["Invoices"]

    assert worksheet["A2"].value == "Sample Vendor"
    assert worksheet["D2"].value == "INV-100"
    assert worksheet["F2"].value == 1000
    assert worksheet["F2"].data_type == "n"
    assert worksheet["K2"].value == 0
