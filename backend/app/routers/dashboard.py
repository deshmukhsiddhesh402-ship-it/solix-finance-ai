"""
Module: Live Financial Dashboard — API layer.

Queries persisted journal entries (see app.models.accounting) for a date
range, computes KPIs via dashboard_engine.py, and offers Excel/PDF export.
If no org_id is provided, aggregates across all data (fine for single-tenant
/ demo use — pass org_id once multi-company support matters).
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
import io

from app.core.db import get_db
from app.services.dashboard_engine import compute_dashboard_kpis, monthly_trend, expense_breakdown
from app.services.report_export_engine import dashboard_to_excel, dashboard_to_pdf

router = APIRouter()


def _load_entries(db: Session, start_date: date, end_date: date, org_id: str | None):
    """Fetch journal lines joined with their account + entry date, in the
    flat dict shape dashboard_engine.py expects."""
    from app.models.accounting import JournalEntry, JournalLine, ChartOfAccount  # local import

    query = (
        db.query(JournalEntry.entry_date, ChartOfAccount.name, ChartOfAccount.account_type,
                  JournalLine.debit, JournalLine.credit)
        .join(JournalLine, JournalLine.journal_id == JournalEntry.id)
        .join(ChartOfAccount, ChartOfAccount.id == JournalLine.account_id)
        .filter(and_(JournalEntry.entry_date >= start_date, JournalEntry.entry_date <= end_date))
    )
    if org_id:
        query = query.filter(JournalEntry.org_id == org_id)

    return [
        {"date": row[0], "account_name": row[1], "account_type": row[2],
         "debit": float(row[3]), "credit": float(row[4])}
        for row in query.all()
    ]


@router.get("/summary")
def dashboard_summary(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    org_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=180))

    entries = _load_entries(db, start, end, org_id)
    kpis = compute_dashboard_kpis(entries)
    trend = monthly_trend(entries)
    breakdown = expense_breakdown(entries)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "kpis": kpis,
        "monthly_trend": trend,
        "expense_breakdown": breakdown,
        "data_points": len(entries),
    }


@router.get("/export/excel")
def export_excel(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    org_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=180))
    entries = _load_entries(db, start, end, org_id)
    kpis = compute_dashboard_kpis(entries)
    trend = monthly_trend(entries)
    breakdown = expense_breakdown(entries)

    xlsx_bytes = dashboard_to_excel(kpis, trend, breakdown)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=solix_dashboard_report.xlsx"},
    )


@router.get("/export/pdf")
def export_pdf(
    org_name: str = Query(default="Your Organization"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    org_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=180))
    entries = _load_entries(db, start, end, org_id)
    kpis = compute_dashboard_kpis(entries)
    trend = monthly_trend(entries)

    period_label = f"{start.isoformat()} to {end.isoformat()}"
    pdf_bytes = dashboard_to_pdf(org_name, period_label, kpis, trend)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=solix_dashboard_report.pdf"},
    )
