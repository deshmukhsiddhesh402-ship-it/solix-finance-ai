from app.services.report_export_engine import dashboard_to_pdf


def test_dashboard_pdf_escapes_user_controlled_text():
    kpis = {
        "revenue": 1000, "expenses": 500, "net_profit": 500,
        "profit_margin_pct": 50, "cash_position": 1000,
        "receivables": 200, "payables": 100, "gst_liability": 0,
        "tds_payable": 0, "working_capital": 1100,
    }
    pdf = dashboard_to_pdf(
        "R&D <North> & Co",
        "FY 2026 <summary> & details",
        kpis,
        [{"month": "Jan <script>", "revenue": 1000, "expenses": 500}],
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
