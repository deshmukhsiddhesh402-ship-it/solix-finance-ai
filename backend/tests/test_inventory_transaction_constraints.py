"""Inventory transaction invariants must be represented in ORM metadata."""


def test_inventory_transaction_metadata_declares_financial_shape_constraints():
    from app.models.accounting import InventoryTransaction

    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in InventoryTransaction.__table__.constraints
        if getattr(constraint, "name", None)
    }

    assert "ck_inventory_transaction_type" in constraints
    assert "ck_inventory_transaction_quantity_positive" in constraints
    assert "ck_inventory_transaction_unit_cost_nonnegative" in constraints
    assert "ck_inventory_transaction_cost_shape" in constraints
    assert "txn_type" in constraints["ck_inventory_transaction_type"]
    assert "quantity > 0" in constraints["ck_inventory_transaction_quantity_positive"]
    assert "unit_cost >= 0" in constraints["ck_inventory_transaction_unit_cost_nonnegative"]
    assert "unit_cost IS NULL" in constraints["ck_inventory_transaction_cost_shape"]


def test_inventory_transaction_constraint_migration_refuses_invalid_legacy_rows():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "008_inventory_transaction_checks.sql"
    ).read_text(encoding="utf-8")

    assert "RAISE EXCEPTION" in migration
    assert "quantity <= 0" in migration
    assert "unit_cost < 0" in migration
    assert "txn_type NOT IN" in migration
    assert "ck_inventory_transaction_cost_shape" in migration
