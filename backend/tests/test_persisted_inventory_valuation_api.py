"""Tenant-scoped persisted inventory valuation API tests."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeQuery:
    def __init__(self, first_value=None, rows=None):
        self.first_value = first_value
        self.rows = rows or []
        self.filters = []
        self.ordering = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, *ordering):
        self.ordering.extend(ordering)
        return self

    def first(self):
        return self.first_value

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, item, transactions):
        self.item_query = FakeQuery(first_value=item)
        self.transactions_query = FakeQuery(rows=transactions)
        self.queries = []

    def query(self, *entities):
        self.queries.append(entities)
        if len(entities) == 1 and getattr(entities[0], "__tablename__", None) == "inventory_items":
            return self.item_query
        return self.transactions_query


def test_persisted_inventory_valuation_uses_ordered_tenant_item_transactions():
    from app.routers.accounting import persisted_inventory_item_valuation

    org_id = uuid4()
    item_id = uuid4()
    item = SimpleNamespace(id=item_id, sku="SKU-100", name="Raw Material", costing_method="FIFO")
    transactions = [
        SimpleNamespace(
            txn_type="purchase",
            txn_date=date(2026, 1, 1),
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("100.0000"),
        ),
        SimpleNamespace(
            txn_type="purchase",
            txn_date=date(2026, 1, 2),
            quantity=Decimal("10.0000"),
            unit_cost=Decimal("120.0000"),
        ),
        SimpleNamespace(
            txn_type="sale",
            txn_date=date(2026, 1, 3),
            quantity=Decimal("12.0000"),
            unit_cost=None,
        ),
    ]
    db = FakeDB(item, transactions)

    result = persisted_inventory_item_valuation(
        item_id=str(item_id),
        org_id=str(org_id),
        db=db,
        _user=str(uuid4()),
    )

    assert result["transaction_count"] == 3
    assert result["valuation"]["cogs"] == 1240.0
    assert result["valuation"]["closing_quantity"] == 8.0
    assert result["valuation"]["closing_inventory_value"] == 960.0
    assert any("inventory_items.org_id" in str(item) for item in db.item_query.filters)
    assert any("inventory_items.id" in str(item) for item in db.item_query.filters)
    assert any("inventory_transactions.item_id" in str(item) for item in db.transactions_query.filters)
    assert len(db.transactions_query.ordering) == 2


def test_persisted_inventory_valuation_does_not_query_transactions_for_foreign_item():
    from app.routers.accounting import persisted_inventory_item_valuation

    db = FakeDB(None, [])
    with pytest.raises(HTTPException) as exc:
        persisted_inventory_item_valuation(
            item_id=str(uuid4()),
            org_id=str(uuid4()),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 404
    assert len(db.queries) == 1


def test_persisted_inventory_valuation_maps_invalid_ledger_to_422():
    from app.routers.accounting import persisted_inventory_item_valuation

    item_id = uuid4()
    item = SimpleNamespace(id=item_id, sku="SKU-200", name="Finished Goods", costing_method="FIFO")
    transactions = [
        SimpleNamespace(
            txn_type="sale",
            txn_date=date(2026, 1, 1),
            quantity=Decimal("1.0000"),
            unit_cost=None,
        )
    ]
    db = FakeDB(item, transactions)

    with pytest.raises(HTTPException) as exc:
        persisted_inventory_item_valuation(
            item_id=str(item_id),
            org_id=str(uuid4()),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert "Stored inventory transactions" in exc.value.detail


def test_persisted_inventory_valuation_rejects_invalid_identifiers():
    from app.routers.accounting import persisted_inventory_item_valuation

    db = FakeDB(None, [])
    with pytest.raises(HTTPException) as exc:
        persisted_inventory_item_valuation(
            item_id="not-a-uuid",
            org_id=str(uuid4()),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
