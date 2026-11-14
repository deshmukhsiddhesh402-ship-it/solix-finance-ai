"""Regression tests for audited, tenant-scoped inventory transaction posting."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


class FakeQuery:
    def __init__(self, first_value=None, rows=None):
        self.first_value = first_value
        self.rows = rows or []
        self.filters = []
        self.ordering = []
        self.for_update = False

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def with_for_update(self):
        self.for_update = True
        return self

    def order_by(self, *ordering):
        self.ordering.extend(ordering)
        return self

    def first(self):
        return self.first_value

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, item, transactions=None, duplicate=None):
        from app.models.accounting import InventoryItem, InventoryTransaction

        self.item_query = FakeQuery(first_value=item)
        self.duplicate_query = FakeQuery(first_value=duplicate)
        self.rows_query = FakeQuery(rows=list(transactions or []))
        self.transaction_query_count = 0
        self.added = []
        self.committed = False
        self.rolled_back = False
        self._inventory_transaction_model = InventoryTransaction
        self._inventory_item_model = InventoryItem

    def query(self, *entities):
        model = entities[0]
        if model is self._inventory_item_model:
            return self.item_query
        if model is self._inventory_transaction_model:
            self.transaction_query_count += 1
            return self.duplicate_query if self.transaction_query_count == 1 else self.rows_query
        return FakeQuery()

    def add(self, value):
        from app.models.accounting import InventoryTransaction

        self.added.append(value)
        if isinstance(value, InventoryTransaction):
            value.id = uuid4()
            value.sequence_no = 101
            self.rows_query.rows.append(value)

    def flush(self):
        return None

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _payload(**overrides):
    from app.routers.accounting import InventoryTransactionCreate

    values = {
        "txn_type": "purchase",
        "txn_date": date(2026, 11, 13),
        "quantity": Decimal("10.0000"),
        "unit_cost": Decimal("2.5000"),
        "reference_no": "  INV-2026-001  ",
    }
    values.update(overrides)
    return InventoryTransactionCreate(**values)


def test_inventory_purchase_is_tenant_locked_audited_and_valued():
    from app.routers.accounting import create_inventory_item_transaction
    from app.models.enterprise import AuditLog

    item_id = uuid4()
    org_id = uuid4()
    user_id = uuid4()
    item = SimpleNamespace(id=item_id, costing_method="FIFO")
    db = FakeDB(item)

    result = create_inventory_item_transaction(
        item_id=str(item_id),
        payload=_payload(),
        org_id=str(org_id),
        db=db,
        _user=str(user_id),
    )

    assert result["reference_no"] == "INV-2026-001"
    assert result["sequence_no"] == 101
    assert result["valuation"]["decimal"]["closing_quantity"] == "10.0000"
    assert result["valuation"]["decimal"]["closing_inventory_value"] == "25.00000000"
    assert db.item_query.for_update is True
    assert any("inventory_items.org_id" in str(value) for value in db.item_query.filters)
    assert any("inventory_items.id" in str(value) for value in db.item_query.filters)
    assert any(isinstance(value, AuditLog) and value.entity_type == "inventory_transaction" for value in db.added)
    assert db.committed is True
    assert db.rolled_back is False


def test_inventory_sale_that_would_make_stock_negative_is_rolled_back():
    from app.routers.accounting import create_inventory_item_transaction

    item_id = uuid4()
    item = SimpleNamespace(id=item_id, costing_method="FIFO")
    existing = SimpleNamespace(
        id=uuid4(),
        txn_type="purchase",
        txn_date=date(2026, 11, 1),
        quantity=Decimal("5.0000"),
        unit_cost=Decimal("10.0000"),
        sequence_no=100,
        reference_no="OPENING-1",
    )
    db = FakeDB(item, [existing])

    with pytest.raises(HTTPException) as exc:
        create_inventory_item_transaction(
            item_id=str(item_id),
            payload=_payload(txn_type="sale", quantity=Decimal("6.0000"), unit_cost=None, reference_no="SALE-1"),
            org_id=str(uuid4()),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert db.rolled_back is True
    assert db.committed is False


def test_duplicate_inventory_reference_is_rejected_before_insert():
    from app.routers.accounting import create_inventory_item_transaction

    item_id = uuid4()
    item = SimpleNamespace(id=item_id, costing_method="FIFO")
    duplicate = SimpleNamespace(id=uuid4(), reference_no="INV-2026-001")
    db = FakeDB(item, duplicate=duplicate)

    with pytest.raises(HTTPException) as exc:
        create_inventory_item_transaction(
            item_id=str(item_id),
            payload=_payload(),
            org_id=str(uuid4()),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 409
    assert not db.added
    assert db.rolled_back is True


def test_foreign_tenant_inventory_item_is_not_disclosed():
    from app.routers.accounting import create_inventory_item_transaction

    db = FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        create_inventory_item_transaction(
            item_id=str(uuid4()),
            payload=_payload(),
            org_id=str(uuid4()),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 404
    assert db.transaction_query_count == 0
    assert db.rolled_back is True


def test_inventory_transaction_request_requires_reference_and_cost_shape():
    with pytest.raises(ValidationError):
        _payload(reference_no="   ")
    with pytest.raises(ValidationError):
        _payload(unit_cost=None)
    with pytest.raises(ValidationError):
        _payload(txn_type="sale")
    with pytest.raises(ValidationError):
        _payload(quantity=True)
    with pytest.raises(ValidationError):
        _payload(txn_type="sale", unit_cost=Decimal("0"))



def test_unrelated_inventory_integrity_failure_is_not_reported_as_duplicate_reference():
    from sqlalchemy.exc import IntegrityError
    from app.routers.accounting import create_inventory_item_transaction

    class FailingFlushDB(FakeDB):
        def flush(self):
            raise IntegrityError("insert inventory transaction", {}, Exception("foreign key violation"))

    item_id = uuid4()
    db = FailingFlushDB(SimpleNamespace(id=item_id, costing_method="FIFO"))
    with pytest.raises(HTTPException) as exc:
        create_inventory_item_transaction(
            item_id=str(item_id),
            payload=_payload(reference_no="NEW-REFERENCE"),
            org_id=str(uuid4()),
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 409
    assert "database constraint" in exc.value.detail
    assert "reference already exists" not in exc.value.detail
    assert db.rolled_back is True
    assert db.committed is False
