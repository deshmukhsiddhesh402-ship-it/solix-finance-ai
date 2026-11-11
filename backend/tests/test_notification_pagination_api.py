"""Notification pagination and per-user isolation regression tests."""
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


def test_notifications_are_paginated_and_count_matches_unread_filter():
    from app.routers.enterprise import list_notifications

    row = SimpleNamespace(
        id=uuid4(), title="Approval needed", body="Review journal entry",
        is_read=False, created_at=datetime(2026, 11, 11, tzinfo=timezone.utc),
    )
    db = FakeDB([row], 1)

    result = list_notifications(
        org_id=str(uuid4()), user_id=None, unread_only=True,
        limit=10, offset=20, db=db, _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["limit"] == 10
    assert result["offset"] == 20
    assert result["notifications"][0]["is_read"] is False
    assert any("notifications.org_id" in str(item) for item in db.rows_query.filters)
    assert any("notifications.user_id" in str(item) for item in db.rows_query.filters)
    assert any("notifications.is_read" in str(item) for item in db.rows_query.filters)
    assert any("notifications.is_read" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 10
    assert db.rows_query.offset_value == 20
    assert len(db.rows_query.ordering) == 2


def test_notifications_reject_user_override_before_database_access():
    from app.routers.enterprise import list_notifications

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_notifications(
            org_id=str(uuid4()), user_id=str(uuid4()), unread_only=False,
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 403
    assert not db.queries


def test_notifications_reject_invalid_organization_before_database_access():
    from app.routers.enterprise import list_notifications

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_notifications(
            org_id="invalid", user_id=None, unread_only=False,
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
