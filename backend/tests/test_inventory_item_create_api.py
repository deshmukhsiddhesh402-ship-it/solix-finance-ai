"""Regression tests for tenant-scoped inventory item creation."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


class FakeQuery:
    def __init__(self, first_value=None):
        self.first_value = first_value
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def first(self):
        return self.first_value


class FakeDB:
    def __init__(self, duplicate=None, fail_flush=False):
        from app.models.accounting import InventoryItem

        self.query_result = FakeQuery(duplicate)
        self.inventory_item_model = InventoryItem
        self.added = []
        self.fail_flush = fail_flush
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        assert model is self.inventory_item_model
        return self.query_result

    def add(self, value):
        self.added.append(value)
        if isinstance(value, self.inventory_item_model):
            value.id = uuid4()

    def flush(self):
        if self.fail_flush:
            raise IntegrityError("insert inventory item", {}, Exception("unique violation"))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _payload(**overrides):
    from app.routers.accounting import InventoryItemCreate

    values = {"sku": " SKU-001 ", "name": " Raw Material ", "costing_method": "FIFO"}
    values.update(overrides)
    return InventoryItemCreate(**values)


def test_inventory_item_create_normalizes_fields_and_writes_audit_log():
    from app.models.enterprise import AuditLog
    from app.routers.accounting import create_inventory_item

    org_id, user_id = uuid4(), uuid4()
    db = FakeDB()
    result = create_inventory_item(
        payload=_payload(), org_id=str(org_id), db=db, _user=str(user_id)
    )

    item = next(value for value in db.added if value.__class__.__name__ == "InventoryItem")
    audit = next(value for value in db.added if isinstance(value, AuditLog))
    assert result["sku"] == "SKU-001"
    assert result["name"] == "Raw Material"
    assert result["costing_method"] == "FIFO"
    assert item.org_id == org_id
    assert item.sku == "SKU-001"
    assert audit.org_id == org_id
    assert audit.user_id == user_id
    assert audit.entity_type == "inventory_item"
    assert db.committed is True
    assert db.rolled_back is False
    assert any("inventory_items.org_id" in str(value) for value in db.query_result.filters)


def test_inventory_item_create_rejects_existing_organization_sku():
    from app.routers.accounting import create_inventory_item

    db = FakeDB(duplicate=object())
    with pytest.raises(HTTPException) as exc:
        create_inventory_item(
            payload=_payload(), org_id=str(uuid4()), db=db, _user=str(uuid4())
        )
    assert exc.value.status_code == 409
    assert db.added == []
    assert db.rolled_back is True
    assert db.committed is False


def test_inventory_item_create_maps_unique_index_race_to_conflict():
    from app.routers.accounting import create_inventory_item

    db = FakeDB(fail_flush=True)
    with pytest.raises(HTTPException) as exc:
        create_inventory_item(
            payload=_payload(), org_id=str(uuid4()), db=db, _user=str(uuid4())
        )
    assert exc.value.status_code == 409
    assert db.rolled_back is True
    assert db.committed is False


@pytest.mark.parametrize("field,value", [
    ("sku", "   "),
    ("name", "   "),
    ("sku", "bad\nSKU"),
    ("name", "bad\x00name"),
])
def test_inventory_item_create_rejects_blank_or_control_text(field, value):
    with pytest.raises(ValidationError):
        _payload(**{field: value})


def test_inventory_item_model_declares_organization_sku_unique_index():
    from app.models.accounting import InventoryItem

    index = next(
        index for index in InventoryItem.__table__.indexes
        if index.name == "uq_inventory_items_org_sku"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == ["org_id", "sku"]


def test_inventory_sku_migration_fails_closed_on_duplicate_legacy_rows():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "010_inventory_item_org_sku_unique.sql"
    ).read_text(encoding="utf-8")

    assert "GROUP BY org_id, sku" in migration
    assert "HAVING COUNT(*) > 1" in migration
    assert "RAISE EXCEPTION" in migration
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_items_org_sku" in migration
