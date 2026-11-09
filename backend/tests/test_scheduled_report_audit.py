"""Regression tests for transactional scheduled-report audit events."""
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import AuditLog, ScheduledReport
from app.routers.enterprise import ScheduledReportRequest, create_scheduled_report


class FakeDB:
    def __init__(self):
        self.added = []
        self.events = []
        self.commit_count = 0
        self.flush_count = 0

    def add(self, row):
        self.added.append(row)
        self.events.append(f"add:{row.__class__.__name__}")

    def flush(self):
        self.flush_count += 1
        self.events.append("flush")
        for row in self.added:
            if isinstance(row, ScheduledReport) and row.id is None:
                row.id = uuid4()

    def commit(self):
        self.commit_count += 1
        self.events.append("commit")


def _audit_rows(db):
    return [row for row in db.added if isinstance(row, AuditLog)]


def test_scheduled_report_creation_audits_safe_metadata_in_same_transaction():
    org_id = uuid4()
    user_id = uuid4()
    db = FakeDB()
    request = ScheduledReportRequest(
        org_id=str(org_id),
        report_type="dashboard_pdf",
        frequency="weekly",
        recipient_emails=["finance@example.com", "owner@example.com"],
    )

    response = create_scheduled_report(
        request,
        org_id=str(org_id),
        db=db,
        _user=str(user_id),
    )

    reports = [row for row in db.added if isinstance(row, ScheduledReport)]
    audits = _audit_rows(db)
    assert len(reports) == 1
    assert len(audits) == 1
    assert response["id"] == str(reports[0].id)
    assert db.flush_count == 1
    assert db.commit_count == 1
    assert db.events == [
        "add:ScheduledReport",
        "flush",
        "add:AuditLog",
        "commit",
    ]

    audit = audits[0]
    assert audit.org_id == org_id
    assert audit.user_id == user_id
    assert audit.action == "create"
    assert audit.entity_type == "scheduled_report"
    assert audit.entity_id == str(reports[0].id)
    assert audit.changes == {
        "report_type": {"before": None, "after": "dashboard_pdf"},
        "frequency": {"before": None, "after": "weekly"},
        "recipient_count": {"before": None, "after": 2},
    }
    assert "finance@example.com" not in repr(audit.changes)
    assert "owner@example.com" not in repr(audit.changes)


def test_scheduled_report_tenant_mismatch_writes_no_rows_or_audit():
    org_id = uuid4()
    request = ScheduledReportRequest(
        org_id=str(uuid4()),
        report_type="dashboard_pdf",
        frequency="weekly",
        recipient_emails=["finance@example.com"],
    )
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        create_scheduled_report(
            request,
            org_id=str(org_id),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert db.added == []
    assert db.flush_count == 0
    assert db.commit_count == 0
