"""Regression tests for spreadsheet formula injection in dashboard exports."""

from io import BytesIO

from openpyxl import load_workbook

from app.services.report_export_engine import dashboard_to_excel


def test_dashboard_excel_treats_expense_labels_as_text():
    content = dashboard_to_excel(
        {"revenue": 100},
        [{"month": "2026-11", "revenue": 100, "expenses": 20}],
        [
            {"name": "=HYPERLINK(\"https://example.invalid\",\"open\")", "value": 10},
            {"name": "Office supplies", "value": 5},
            {"name": "  @SUM(A1:A2)", "value": 1},
        ],
    )

    workbook = load_workbook(BytesIO(content), data_only=False)
    sheet = workbook["Expense Breakdown"]

    assert sheet["A2"].value.startswith("'=")
    assert sheet["A2"].data_type == "s"
    assert sheet["A3"].value == "Office supplies"
    assert sheet["A4"].value.startswith("'  @")
    assert sheet["A4"].data_type == "s"
