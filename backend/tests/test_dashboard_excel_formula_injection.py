from io import BytesIO

from openpyxl import load_workbook

from app.services.report_export_engine import dashboard_to_excel


def test_dashboard_excel_export_neutralizes_formula_leading_text():
    payload = dashboard_to_excel(
        {"note": "=HYPERLINK(\"https://evil.example\",\"click\")"},
        [{"month": "+SUM(A1:A2)", "revenue": 100}],
        [{"category": "@cmd", "amount": 10}],
    )
    workbook = load_workbook(BytesIO(payload), data_only=False)
    assert workbook["KPI Summary"]["B1"].value.startswith("'=")
    assert workbook["Monthly Trend"]["A2"].value.startswith("'+")
    assert workbook["Expense Breakdown"]["A2"].value.startswith("'@")
    workbook.close()
