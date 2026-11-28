from io import BytesIO

from openpyxl import load_workbook

from app.services.invoice_ocr_engine import invoices_to_excel


def test_invoice_export_writes_formula_leading_text_as_literal_cells():
    payload = invoices_to_excel([{
        "vendor_name": '=HYPERLINK("https://evil.example","click")',
        "vendor_gstin": "+123456789012345",
        "invoice_number": "@SUM(A1:A2)",
        "invoice_date": "-cmd|/C calc",
        "taxable_value": 100,
        "cgst_amount": 9,
        "sgst_amount": 9,
        "igst_amount": 0,
        "total_amount": 118,
        "line_items": [],
    }])
    workbook = load_workbook(BytesIO(payload), data_only=False)
    sheet = workbook["Invoices"]
    assert sheet["A2"].data_type != "f"
    assert sheet["A2"].value.startswith("'=")
    assert sheet["B2"].value.startswith("'+")
    assert sheet["D2"].value.startswith("'@")
    assert sheet["E2"].value.startswith("'-")
    workbook.close()
