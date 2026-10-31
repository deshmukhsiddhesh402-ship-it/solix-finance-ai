"""Regression tests for formula injection in generated Excel exports."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.excel_automation import _sanitize_excel_formula_values


def test_excel_export_escapes_formula_like_text_but_preserves_numeric_values():
    frame = pd.DataFrame(
        {
            "description": ["=HYPERLINK(\"https://evil.example\",\"open\")", "  +cmd", "-1+2", "@SUM(A1:A2)", "ordinary"],
            "amount": [-125.50, 0, 42, 7, 9],
        }
    )

    safe = _sanitize_excel_formula_values(frame)

    assert safe["description"].tolist() == [
        "'=HYPERLINK(\"https://evil.example\",\"open\")",
        "'  +cmd",
        "'-1+2",
        "'@SUM(A1:A2)",
        "ordinary",
    ]
    assert safe["amount"].tolist() == [-125.50, 0, 42, 7, 9]
    assert frame.iloc[0, 0].startswith("=")


def test_excel_export_escapes_leading_tab_or_newline_before_formula():
    frame = pd.DataFrame({"value": ["\t=1+1", "\n@SUM(A1:A2)"]})

    safe = _sanitize_excel_formula_values(frame)

    assert safe["value"].tolist() == ["'\t=1+1", "'\n@SUM(A1:A2)"]
