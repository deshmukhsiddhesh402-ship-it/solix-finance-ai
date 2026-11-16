"""Regression tests for tenant-scoped fixed asset audit history."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeQuery:
    def __init__(self, first_value=None, rows=None, scalar_value=None):
        self.first_value = first_value
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

    def first(self):
        return self.first_value

    def scalar(self):
        return self.scalar_value

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, asset, rows=None, total=0):
        self.asset_query = FakeQuery(first_value=asset)
        self.history_query = FakeQuery(rows=rows)
        self.count_query = FakeQuery(scalar_value=total)
        self.queries = []

    def query(self, *entities):
        self.queries.append(entities)
        if len(entities) == 1 and getattr(entities[0], "__tablename__", None) == "fixed_assets":
            return self.asset_query
        if len(entities) == 1 and getattr(entities[0], "name", None) == "count":
            return self.count_query
        return self.history_query


def test_fixed_asset_audit_history_is_tenant_scoped_and_paginated():
    from app.routers.accounting import list_fixed_asset_audit_history

    asset_id, org_id, user_id = uuid4(), uuid4(), uuid4()
    event = SimpleNamespace(
        id=uuid4(), user_id=user_id, action="edit",
        changes={"cost": {"old": "800000.00", "new": "850000.00"}},
        created_at=datetime(2026, 11, 16, tzinfo=timezone.utc),
    )
    db = FakeDB(SimpleNamespace(id=asset_id), [event], total=1)
    result = list_fixed_asset_audit_history(
        asset_id=str(asset_id), org_id=str(org_id),
        limit=10, offset=5, db=db, _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["events"][0]["action"] == "edit"
    assert result["events"][0]["user_id"] == str(user_id)
    assert result["events"][0]["changes"]["cost"]["new"] == "850000.00"
    assert any("fixed_assets.org_id" in str(value) for value in db.asset_query.filters)
    assert any("audit_logs.org_id" in str(value) for value in db.history_query.filters)
    assert any("audit_logs.entity_type" in str(value) for value in db.history_query.filters)
    assert any("audit_logs.entity_id" in str(value) for value in db.history_query.filters)
    assert db.history_query.limit_value == 10
    assert db.history_query.offset_value == 5
    assert len(db.history_query.ordering) == 2


def test_fixed_asset_audit_history_does_not_query_foreign_asset_events():
    from app.routers.accounting import list_fixed_asset_audit_history

    db = FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        list_fixed_asset_audit_history(
            asset_id=str(uuid4()), org_id=str(uuid4()),
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 404
    assert len(db.queries) == 1


def test_fixed_asset_audit_history_rejects_invalid_identifiers_before_queries():
    from app.routers.accounting import list_fixed_asset_audit_history

    db = FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        list_fixed_asset_audit_history(
            asset_id="bad-id", org_id=str(uuid4()),
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 400
    assert not db.queries


def test_fixed_asset_audit_history_requires_audit_log_view_permission():
    from app.routers.accounting import router

    route = next(
        route for route in router.routes
        if getattr(route, "path", None) == "/fixed-assets/{asset_id}/audit-history"
    )
    dependency = next(
        dependency.call for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    assert (closure["resource"], closure["action"]) == ("audit_log", "view")
