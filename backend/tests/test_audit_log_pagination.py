"""Tests for bounded, deterministic audit-log pagination."""
from inspect import signature
from pathlib import Path
import sys
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import AuditLog
from app.routers.enterprise import view_audit_log


class FakeQuery:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.ordering = ()
        self.limit_value = None
        self.offset_value = None

    def filter(self, *criteria):
        return self

    def order_by(self, *expressions):
        self.ordering = expressions
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, query):
        self.query_obj = query

    def query(self, model):
        assert model is AuditLog
        return self.query_obj


def _row(row_id):
    from datetime import datetime, timezone

    return AuditLog(
        id=row_id,
        org_id=uuid4(),
        user_id=uuid4(),
        action="create",
        entity_type="journal_entry",
        entity_id="entry-1",
        changes=None,
        created_at=datetime(2026, 11, 8, tzinfo=timezone.utc),
    )


def test_audit_log_uses_default_offset_and_bounded_page_size():
    org_id = uuid4()
    query = FakeQuery()
    offset_parameter = signature(view_audit_log).parameters["offset"].default
    limit_parameter = signature(view_audit_log).parameters["limit"].default

    response = view_audit_log(
        org_id=str(org_id),
        limit=limit_parameter.default,
        db=FakeDB(query),
        _user=str(uuid4()),
        offset=offset_parameter.default,
    )

    assert response == {"entries": []}
    assert offset_parameter.default == 0
    assert offset_parameter.ge == 0
    assert offset_parameter.le == 10000
    assert limit_parameter.default == 50
    assert limit_parameter.le == 200
    assert query.limit_value == 50
    assert query.offset_value == 0


def test_audit_log_applies_explicit_offset_and_unique_ordering():
    org_id = uuid4()
    rows = [_row(uuid4())]
    query = FakeQuery(rows)

    response = view_audit_log(
        org_id=str(org_id),
        limit=25,
        db=FakeDB(query),
        _user=str(uuid4()),
        offset=75,
    )

    ordered_columns = [
        getattr(getattr(expression, "element", expression), "key", None)
        for expression in query.ordering
    ]
    assert query.limit_value == 25
    assert query.offset_value == 75
    assert ordered_columns == ["created_at", "id"]
    assert len(response["entries"]) == 1
    assert response["entries"][0]["id"] == str(rows[0].id)
