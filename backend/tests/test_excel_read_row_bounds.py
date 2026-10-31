"""Regression tests for bounded XLSX row materialization."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import excel_automation


def test_xlsx_reader_caps_rows_before_dataframe_materialization(monkeypatch):
    observed = {}

    def fake_read_excel(stream, **kwargs):
        observed.update(kwargs)
        return pd.DataFrame({"value": [1]})

    monkeypatch.setattr(excel_automation, "_validate_excel_archive", lambda payload: None)
    monkeypatch.setattr(excel_automation.pd, "read_excel", fake_read_excel)

    result = excel_automation._read_upload_to_df("ledger.xlsx", b"placeholder")

    assert len(result) == 1
    assert observed["nrows"] == excel_automation.MAX_ROWS + 1


def test_xlsm_reader_also_uses_bounded_row_count(monkeypatch):
    observed = {}

    def fake_read_excel(stream, **kwargs):
        observed.update(kwargs)
        return pd.DataFrame({"value": [1]})

    monkeypatch.setattr(excel_automation, "_validate_excel_archive", lambda payload: None)
    monkeypatch.setattr(excel_automation.pd, "read_excel", fake_read_excel)

    excel_automation._read_upload_to_df("ledger.xlsm", b"placeholder")

    assert observed["nrows"] == excel_automation.MAX_ROWS + 1
