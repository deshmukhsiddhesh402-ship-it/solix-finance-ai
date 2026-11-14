"""Idempotent inventory migrations must check constraints on the intended table."""


def test_inventory_transaction_migration_scopes_constraint_names_to_table():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "008_inventory_transaction_checks.sql"
    ).read_text(encoding="utf-8")

    assert migration.count("conrelid = 'inventory_transactions'::regclass") == 4


def test_inventory_costing_method_migration_scopes_constraint_name_to_table():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "009_inventory_costing_method_check.sql"
    ).read_text(encoding="utf-8")

    assert "conrelid = 'inventory_items'::regclass" in migration
