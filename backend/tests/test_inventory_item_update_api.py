"""Regression tests for safe, tenant-scoped inventory item updates."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


class FakeQuery:
    def __init__(self, first_value=None):
        self.first_value = first_value
        self.filters = []
        self.for_update = False

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def with_for_update(self):
        self.for_update = True
        return self

    def first(self):
        return self.first_value


class FakeDB:
    def __init__(self, item, duplicate=None, transaction=None, fail_commit=False):
        from app.models.accounting import InventoryItem, InventoryTransaction

        self.item_model = InventoryItem
        self.transaction_model = InventoryTransaction
        self.item = item
        self.duplicate = duplicate
        self.transaction = transaction
        self.item_query_count = 0
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.fail_commit = fail_commit
        self.item_queries = []
        self.transaction_query = None

    def query(self, model):
        if model is self.item_model:
            self.item_query_count += 1
            value = self.item if self.item_query_count == 1 else self.duplicate
            query = FakeQuery(value)
            self.item_queries.append(query)
            return query
        if model is self.transaction_model:
            self.transaction_query = FakeQuery(self.transaction)
            return self.transaction_query
        raise AssertionError(f"Unexpected query model: {model}")

    def add(self, value):
        self.added.append(value)

    def commit(self):
        if self.fail_commit:
            raise IntegrityError("update inventory item", {}, Exception("unique violation"))
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _payload(**overrides):
    from app.routers.accounting import InventoryItemUpdate

    return InventoryItemUpdate(**overrides)


def test_inventory_item_update_audits_metadata_changes():
    from app.models.enterprise import AuditLog
    from app.routers.accounting import update_inventory_item

    item_id, org_id, user_id = uuid4(), uuid4(), uuid4()
    item = SimpleNamespace(id=item_id, org_id=org_id, sku="SKU-1", name="Old Name", costing_method="FIFO")
    db = FakeDB(item)
    result = update_inventory_item(
        item_id=str(item_id), payload=_payload(name=" New Name "),
        org_id=str(org_id), db=db, _user=str(user_id),
    )

    audit = next(value for value in db.added if isinstance(value, AuditLog))
    assert result["name"] == "New Name"
    assert item.name == "New Name"
    assert audit.action == "edit"
    assert audit.entity_type == "inventory_item"
    assert audit.changes == {"name": {"old": "Old Name", "new": "New Name"}}
    assert db.item_queries[0].for_update is True
    assert db.committed is True
    assert db.rolled_back is False


def test_inventory_item_update_blocks_costing_method_change_after_postings():
    from app.routers.accounting import update_inventory_item

    item_id, org_id = uuid4(), uuid4()
    item = SimpleNamespace(id=item_id, org_id=org_id, sku="SKU-1", name="Raw", costing_method="FIFO")
    db = FakeDB(item, transaction=object())
    with pytest.raises(HTTPException) as exc:
        update_inventory_item(
            item_id=str(item_id), payload=_payload(costing_method="WAVG"),
            org_id=str(org_id), db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 409
    assert item.costing_method == "FIFO"
    assert db.committed is False
    assert db.rolled_back is True


def test_inventory_item_update_allows_costing_method_change_before_first_transaction():
    from app.routers.accounting import update_inventory_item

    item_id, org_id = uuid4(), uuid4()
    item = SimpleNamespace(id=item_id, org_id=org_id, sku="SKU-1", name="Raw", costing_method="FIFO")
    db = FakeDB(item)
    result = update_inventory_item(
        item_id=str(item_id), payload=_payload(costing_method="WAVG"),
        org_id=str(org_id), db=db, _user=str(uuid4()),
    )
    assert result["costing_method"] == "WAVG"
    assert db.transaction_query.first_value is None
    assert db.committed is True


def test_inventory_item_update_rejects_duplicate_sku():
    from app.routers.accounting import update_inventory_item

    item_id, org_id = uuid4(), uuid4()
    item = SimpleNamespace(id=item_id, org_id=org_id, sku="SKU-1", name="Raw", costing_method="FIFO")
    db = FakeDB(item, duplicate=object())
    with pytest.raises(HTTPException) as exc:
        update_inventory_item(
            item_id=str(item_id), payload=_payload(sku="SKU-2"),
            org_id=str(org_id), db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 409
    assert item.sku == "SKU-1"
    assert db.rolled_back is True


def test_inventory_item_update_maps_unique_index_race_to_conflict():
    from app.routers.accounting import update_inventory_item

    item_id, org_id = uuid4(), uuid4()
    item = SimpleNamespace(id=item_id, org_id=org_id, sku="SKU-1", name="Raw", costing_method="FIFO")
    db = FakeDB(item, fail_commit=True)
    with pytest.raises(HTTPException) as exc:
        update_inventory_item(
            item_id=str(item_id), payload=_payload(sku="SKU-2"),
            org_id=str(org_id), db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 409
    assert db.rolled_back is True
    assert db.committed is False


@pytest.mark.parametrize("data", [{}, {"name": None}, {"sku": "  "}, {"name": "bad\nname"}])
def test_inventory_item_update_rejects_empty_null_or_control_text(data):
    with pytest.raises(ValidationError):
        _payload(**data)


def test_inventory_item_update_requires_inventory_edit_permission():
    from app.routers.accounting import router

    route = next(route for route in router.routes if getattr(route, "path", None) == "/inventory/items/{item_id}")
    dependency = next(
        dependency.call for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    assert (closure["resource"], closure["action"]) == ("inventory", "edit")
