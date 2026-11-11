"""Tenant-scoped inventory item register regression tests."""
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


def test_inventory_item_register_scopes_tenant_and_supports_method_search():
    from app.routers.accounting import list_inventory_items

    item = SimpleNamespace(
        id=uuid4(), sku="RAW-001", name="Raw Material", costing_method="WAVG",
    )
    db = FakeDB([item], 1)

    result = list_inventory_items(
        org_id=str(uuid4()), costing_method="WAVG", search=" raw ",
        limit=20, offset=0, db=db, _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["items"][0]["sku"] == "RAW-001"
    assert result["items"][0]["costing_method"] == "WAVG"
    assert any("inventory_items.org_id" in str(item) for item in db.rows_query.filters)
    assert any("inventory_items.org_id" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 20
    assert db.rows_query.offset_value == 0
    assert len(db.rows_query.ordering) == 3


def test_inventory_item_register_rejects_blank_search_before_queries():
    from app.routers.accounting import list_inventory_items

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_inventory_items(
            org_id=str(uuid4()), costing_method=None, search="   ",
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_inventory_item_register_rejects_invalid_tenant_before_queries():
    from app.routers.accounting import list_inventory_items

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_inventory_items(
            org_id="invalid", costing_method=None, search=None,
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
