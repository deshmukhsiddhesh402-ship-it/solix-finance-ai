"""Inventory rows must always have an explicit tenant and parent item."""


def test_inventory_orm_requires_tenant_and_item_ownership():
    from app.models.accounting import InventoryItem, InventoryTransaction

    assert InventoryItem.__table__.c.org_id.nullable is False
    assert InventoryTransaction.__table__.c.item_id.nullable is False


def test_inventory_ownership_migration_fails_closed_on_orphan_rows():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "007_inventory_tenant_ownership_not_null.sql"
    ).read_text(encoding="utf-8")

    assert "inventory_items WHERE org_id IS NULL" in migration
    assert "inventory_transactions WHERE item_id IS NULL" in migration
    assert "RAISE EXCEPTION" in migration
    assert "ALTER COLUMN org_id SET NOT NULL" in migration
    assert "ALTER COLUMN item_id SET NOT NULL" in migration
