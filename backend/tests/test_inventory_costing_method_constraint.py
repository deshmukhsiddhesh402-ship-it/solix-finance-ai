"""Inventory costing methods must match the valuation engine's supported methods."""


def test_inventory_item_metadata_restricts_costing_method():
    from app.models.accounting import InventoryItem

    constraint = next(
        constraint for constraint in InventoryItem.__table__.constraints
        if constraint.name == "ck_inventory_item_costing_method"
    )
    assert "FIFO" in str(constraint.sqltext)
    assert "LIFO" in str(constraint.sqltext)
    assert "WAVG" in str(constraint.sqltext)


def test_inventory_costing_method_migration_fails_closed_on_unsupported_rows():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "009_inventory_costing_method_check.sql"
    ).read_text(encoding="utf-8")

    assert "costing_method NOT IN ('FIFO', 'LIFO', 'WAVG')" in migration
    assert "RAISE EXCEPTION" in migration
    assert "ck_inventory_item_costing_method" in migration
