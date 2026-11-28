from io import BytesIO

import pandas as pd
from openpyxl import load_workbook

import app.routers.excel_automation as excel


def test_download_cleaned_file_neutralizes_formula_leading_text(monkeypatch):
    frame = pd.DataFrame({
        "vendor": ['=HYPERLINK("https://evil.example","click")'],
        "reference": ["+SUM(A1:A2)"],
        "note": ["@cmd"],
        "description": ["-1+2"],
    })
    monkeypatch.setattr(excel, "_get_cleaned_session", lambda *_args: {"df": frame})
    response = excel.download_cleaned_file(
        "11111111-1111-4111-8111-111111111111",
        org_id="22222222-2222-4222-8222-222222222222",
        _user="33333333-3333-4333-8333-333333333333",
    )
    payload = response.body
    workbook = load_workbook(BytesIO(payload), data_only=False)
    sheet = workbook["Cleaned Data"]
    assert sheet["A2"].data_type != "f"
    assert sheet["A2"].value.startswith("'=")
    assert sheet["B2"].value.startswith("'+")
    assert sheet["C2"].value.startswith("'@")
    assert sheet["D2"].value.startswith("'-")
    workbook.close()
