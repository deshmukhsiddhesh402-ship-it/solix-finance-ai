"""Tenant-scoped inventory transaction ledger regression tests."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeQuery:
    def __init__(self, rows=None, scalar_value=None, first_value=None):
        self.rows = rows or []
        self.scalar_value = scalar_value
        self.first_value = first_value
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

    def first(self):
        return self.first_value


class FakeDB:
    def __init__(self, item, rows, total):
        self.item_query = FakeQuery(first_value=item)
        self.rows_query = FakeQuery(rows)
        self.count_query = FakeQuery(scalar_value=total)
        self.queries = []

    def query(self, *entities):
        self.queries.append(entities)
        if len(entities) == 1 and getattr(entities[0], "name", None) == "count":
            return self.count_query
        if len(entities) == 1 and getattr(entities[0], "__name__", "") == "InventoryItem":
            return self.item_query
        return self.rows_query


def test_inventory_transaction_ledger_verifies_item_tenant_and_paginates():
    from app.routers.accounting import list_inventory_item_transactions

    item_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(), txn_type="purchase", txn_date=date(2026, 11, 10),
        quantity=Decimal("12.5000"), unit_cost=Decimal("80.2500"),
    )
    db = FakeDB(SimpleNamespace(id=item_id), [row], 1)

    result = list_inventory_item_transactions(
        item_id=str(item_id), org_id=str(uuid4()),
        start_date=date(2026, 11, 1), end_date=date(2026, 11, 30),
        txn_type="purchase", limit=10, offset=5, db=db, _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["transactions"][0]["quantity"] == 12.5
    assert result["transactions"][0]["unit_cost"] == 80.25
    assert "same-day sequence field" in result["ordering_note"]
    assert any("inventory_items.org_id" in str(item) for item in db.item_query.filters)
    assert any("inventory_transactions.item_id" in str(item) for item in db.rows_query.filters)
    assert any("inventory_transactions.item_id" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 10
    assert db.rows_query.offset_value == 5
    assert len(db.rows_query.ordering) == 2


def test_inventory_transaction_ledger_does_not_disclose_foreign_tenant_item():
    from app.routers.accounting import list_inventory_item_transactions

    db = FakeDB(None, [], 0)
    with pytest.raises(HTTPException) as exc:
        list_inventory_item_transactions(
            item_id=str(uuid4()), org_id=str(uuid4()),
            start_date=None, end_date=None, txn_type=None,
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 404
    assert len(db.queries) == 1


def test_inventory_transaction_ledger_rejects_reversed_date_range_before_queries():
    from app.routers.accounting import list_inventory_item_transactions

    db = FakeDB(None, [], 0)
    with pytest.raises(HTTPException) as exc:
        list_inventory_item_transactions(
            item_id=str(uuid4()), org_id=str(uuid4()),
            start_date=date(2026, 11, 30), end_date=date(2026, 11, 1),
            txn_type=None, limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_inventory_transaction_ledger_rejects_invalid_identifiers_before_queries():
    from app.routers.accounting import list_inventory_item_transactions

    db = FakeDB(None, [], 0)
    with pytest.raises(HTTPException) as exc:
        list_inventory_item_transactions(
            item_id="bad-item", org_id=str(uuid4()),
            start_date=None, end_date=None, txn_type=None,
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
