from datetime import datetime, timezone
from types import SimpleNamespace

from app.routers.enterprise import view_audit_log


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.offset_value = None
        self.limit_value = None

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows[:self.limit_value]


class FakeDB:
    def __init__(self, rows):
        self.query_obj = FakeQuery(rows)

    def query(self, _model):
        return self.query_obj


def test_audit_log_returns_bounded_pages_and_next_offset():
    rows = [
        SimpleNamespace(
            id=f"id-{i}", user_id=None, action="update",
            entity_type="invoice", entity_id=str(i), changes={},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        for i in range(3)
    ]
    db = FakeDB(rows)
    result = view_audit_log(
        org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        limit=2,
        offset=4,
        db=db,
        _user="11111111-1111-4111-8111-111111111111",
    )
    assert len(result["entries"]) == 2
    assert result["has_more"] is True
    assert result["next_offset"] == 6
    assert db.query_obj.offset_value == 4
    assert db.query_obj.limit_value == 3


def test_audit_log_last_page_has_no_next_offset():
    db = FakeDB([])
    result = view_audit_log(
        org_id="6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22",
        limit=50,
        offset=100,
        db=db,
        _user="11111111-1111-4111-8111-111111111111",
    )
    assert result["has_more"] is False
    assert result["next_offset"] is None
