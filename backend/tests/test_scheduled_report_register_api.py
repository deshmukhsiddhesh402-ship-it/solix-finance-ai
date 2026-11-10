"""Tenant-scoped scheduled-report register API regression tests."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeQuery:
    def __init__(self, rows=None, scalar_value=None):
        self.rows = rows or []
        self.scalar_value = scalar_value
        self.filters = []
        self.ordering = []
        self.offset_value = None
        self.limit_value = None

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, *ordering):
        self.ordering.extend(ordering)
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows

    def scalar(self):
        return self.scalar_value


class FakeDB:
    def __init__(self, rows, total):
        self.rows_query = FakeQuery(rows)
        self.count_query = FakeQuery(scalar_value=total)
        self.queries = []

    def query(self, *entities):
        self.queries.append(entities)
        if len(entities) == 1 and getattr(entities[0], "name", None) == "count":
            return self.count_query
        return self.rows_query


def test_scheduled_report_register_returns_metadata_without_recipient_addresses():
    from app.routers.enterprise import list_scheduled_reports

    org_id = uuid4()
    report = SimpleNamespace(
        id=uuid4(),
        report_type="dashboard_pdf",
        frequency="weekly",
        is_active=True,
        recipient_emails=["finance@example.com", "owner@example.com"],
        created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        last_sent_at=None,
    )
    db = FakeDB([report], total=1)

    result = list_scheduled_reports(
        org_id=str(org_id),
        limit=25,
        offset=0,
        db=db,
        _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["scheduled_reports"][0]["recipient_count"] == 2
    assert "recipient_emails" not in result["scheduled_reports"][0]
    assert any("scheduled_reports.org_id" in str(item) for item in db.rows_query.filters)
    assert any("scheduled_reports.org_id" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 25
    assert db.rows_query.offset_value == 0
    assert len(db.rows_query.ordering) == 2


def test_scheduled_report_register_rejects_invalid_organization_identifier():
    from app.routers.enterprise import list_scheduled_reports

    db = FakeDB([], total=0)
    with pytest.raises(HTTPException) as exc:
        list_scheduled_reports(
            org_id="invalid",
            limit=50,
            offset=0,
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries


def test_scheduled_report_register_handles_legacy_non_list_recipient_metadata():
    from app.routers.enterprise import list_scheduled_reports

    report = SimpleNamespace(
        id=uuid4(),
        report_type="dashboard_excel",
        frequency="monthly",
        is_active=False,
        recipient_emails={"legacy": "malformed"},
        created_at=None,
        last_sent_at=None,
    )
    db = FakeDB([report], total=1)

    result = list_scheduled_reports(
        org_id=str(uuid4()),
        limit=50,
        offset=0,
        db=db,
        _user=str(uuid4()),
    )

    assert result["scheduled_reports"][0]["recipient_count"] is None
    assert result["scheduled_reports"][0]["is_active"] is False
