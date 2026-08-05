"""
Module: Live Financial Dashboard — report export (Excel + PDF).
"""
import io
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm


def dashboard_to_excel(kpis: dict, monthly: list[dict], expense_breakdown_rows: list[dict]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame([kpis]).T.rename(columns={0: "Value"}).to_excel(writer, sheet_name="KPI Summary")
        pd.DataFrame(monthly).to_excel(writer, index=False, sheet_name="Monthly Trend")
        pd.DataFrame(expense_breakdown_rows).to_excel(writer, index=False, sheet_name="Expense Breakdown")
    buffer.seek(0)
    return buffer.read()


def _inr(n) -> str:
    if n is None:
        return "—"
    return f"Rs {n:,.2f}"


def dashboard_to_pdf(org_name: str, period_label: str, kpis: dict, monthly: list[dict]) -> bytes:
    """Build a one-page financial summary report as a PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"{org_name} — Financial Summary", styles["Title"]))
    story.append(Paragraph(period_label, styles["Normal"]))
    story.append(Spacer(1, 16))

    kpi_rows = [
        ["Metric", "Value"],
        ["Revenue", _inr(kpis["revenue"])],
        ["Expenses", _inr(kpis["expenses"])],
        ["Net Profit", _inr(kpis["net_profit"])],
        ["Profit Margin", f"{kpis['profit_margin_pct']}%" if kpis["profit_margin_pct"] is not None else "—"],
        ["Cash Position", _inr(kpis["cash_position"])],
        ["Receivables", _inr(kpis["receivables"])],
        ["Payables", _inr(kpis["payables"])],
        ["GST Liability", _inr(kpis["gst_liability"])],
        ["TDS Payable", _inr(kpis["tds_payable"])],
        ["Working Capital", _inr(kpis["working_capital"])],
    ]
    kpi_table = Table(kpi_rows, colWidths=[8 * cm, 8 * cm])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312e81")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f8")]),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 20))

    if monthly:
        story.append(Paragraph("Monthly Revenue vs Expenses", styles["Heading2"]))
        trend_rows = [["Month", "Revenue", "Expenses", "Net"]] + [
            [m["month"], _inr(m["revenue"]), _inr(m["expenses"]), _inr(m["revenue"] - m["expenses"])]
            for m in monthly
        ]
        trend_table = Table(trend_rows, colWidths=[4 * cm, 4 * cm, 4 * cm, 4 * cm])
        trend_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312e81")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f8")]),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))
        story.append(trend_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
