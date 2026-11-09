"""Regression tests for untrusted dashboard PDF title text."""

from app.services import report_export_engine


def test_dashboard_pdf_escapes_organization_name_before_paragraph(monkeypatch):
    paragraph_text = []

    class _Document:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, story):
            pass

    def _paragraph(text, style):
        paragraph_text.append(text)
        return object()

    monkeypatch.setattr(report_export_engine, "SimpleDocTemplate", _Document)
    monkeypatch.setattr(report_export_engine, "Paragraph", _paragraph)

    report_export_engine.dashboard_to_pdf(
        "R&D <Partners>",
        "2026-11-01 to 2026-11-30",
        {
            "revenue": 0,
            "expenses": 0,
            "net_profit": 0,
            "profit_margin_pct": None,
            "cash_position": 0,
            "receivables": 0,
            "payables": 0,
            "gst_liability": 0,
            "tds_payable": 0,
            "working_capital": 0,
        },
        [],
    )

    assert paragraph_text[0] == "R&amp;D &lt;Partners&gt; — Financial Summary"
