"""Module: Live Financial Dashboard — tenant-scoped API layer."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_
import io
import uuid

from app.core.db import get_db
from app.services.dashboard_engine import compute_dashboard_kpis, monthly_trend, expense_breakdown
from app.services.report_export_engine import dashboard_to_excel, dashboard_to_pdf
from app.routers.enterprise import require_permission

router = APIRouter()


def _load_entries(db: Session, start_date: date, end_date: date, org_id: uuid.UUID):
    from app.models.accounting import JournalEntry, JournalLine, ChartOfAccount

    query = (
        db.query(JournalEntry.entry_date, ChartOfAccount.name, ChartOfAccount.account_type,
                 JournalLine.debit, JournalLine.credit)
        .join(JournalLine, JournalLine.journal_id == JournalEntry.id)
        .join(ChartOfAccount, ChartOfAccount.id == JournalLine.account_id)
        .filter(and_(JournalEntry.entry_date >= start_date, JournalEntry.entry_date <= end_date))
        .filter(JournalEntry.org_id == org_id, ChartOfAccount.org_id == org_id)
    )
    return [
        {"date": row[0], "account_name": row[1], "account_type": row[2],
         "debit": float(row[3]), "credit": float(row[4])}
        for row in query.all()
    ]


def _date_range(start_date: date | None, end_date: date | None):
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=180))
    if start > end:
        raise HTTPException(400, detail="start_date must be on or before end_date.")
    return start, end


@router.get("/summary")
def dashboard_summary(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    start, end = _date_range(start_date, end_date)
    entries = _load_entries(db, start, end, org_uuid)
    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "kpis": compute_dashboard_kpis(entries),
        "monthly_trend": monthly_trend(entries),
        "expense_breakdown": expense_breakdown(entries),
        "data_points": len(entries),
    }


@router.get("/export/excel")
def export_excel(
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    start, end = _date_range(start_date, end_date)
    entries = _load_entries(db, start, end, org_uuid)
    kpis, trend, breakdown = compute_dashboard_kpis(entries), monthly_trend(entries), expense_breakdown(entries)
    return StreamingResponse(
        io.BytesIO(dashboard_to_excel(kpis, trend, breakdown)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=solix_dashboard_report.xlsx"},
    )


@router.get("/export/pdf")
def export_pdf(
    org_name: str = Query(default="Your Organization"),
    start_date: date = Query(default=None),
    end_date: date = Query(default=None),
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("reports", "view")),
):
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc
    start, end = _date_range(start_date, end_date)
    entries = _load_entries(db, start, end, org_uuid)
    return StreamingResponse(
        io.BytesIO(dashboard_to_pdf(org_name, f"{start.isoformat()} to {end.isoformat()}", compute_dashboard_kpis(entries), monthly_trend(entries))),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=solix_dashboard_report.pdf"},
    )
