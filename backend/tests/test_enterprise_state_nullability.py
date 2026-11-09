"""Regression coverage for non-null enterprise lifecycle state flags."""
from pathlib import Path
import re
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import ApiKey, Notification, ScheduledReport


def _table_definition(sql: str, table: str) -> str:
    match = re.search(
        rf"CREATE TABLE\s+{re.escape(table)}\s*\((.*?)\n\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None, f"missing CREATE TABLE for {table}"
    return match.group(1)


def test_enterprise_state_flags_are_non_nullable_in_orm():
    assert ApiKey.__table__.c.revoked.nullable is False
    assert ScheduledReport.__table__.c.is_active.nullable is False
    assert Notification.__table__.c.is_read.nullable is False


def test_canonical_schema_already_requires_non_null_state_flags():
    schema = (ROOT_DIR / "database" / "schema.sql").read_text(encoding="utf-8")
    expected = {
        "api_keys": "revoked",
        "scheduled_reports": "is_active",
        "notifications": "is_read",
    }
    for table, column in expected.items():
        definition = _table_definition(schema, table)
        assert re.search(
            rf"^\s*{column}\s+BOOLEAN\s+NOT NULL\b",
            definition,
            flags=re.IGNORECASE | re.MULTILINE,
        ), f"{table}.{column} must remain NOT NULL in schema.sql"


def test_state_migration_preflights_nulls_before_altering_columns():
    migration = (
        ROOT_DIR
        / "database"
        / "migrations"
        / "006_enterprise_state_not_null.sql"
    ).read_text(encoding="utf-8")
    preflight = migration.split("ALTER TABLE", 1)[0]
    expected = {
        "api_keys": "revoked",
        "scheduled_reports": "is_active",
        "notifications": "is_read",
    }
    for table, column in expected.items():
        assert re.search(
            rf"FROM\s+{table}\s+WHERE\s+{column}\s+IS NULL",
            preflight,
            flags=re.IGNORECASE,
        ), f"migration must preflight {table}.{column}"

    assert preflight.count("RAISE EXCEPTION") == len(expected)
    assert migration.count("ALTER TABLE") == len(expected)
    assert "UPDATE " not in migration.upper()
    assert "DELETE FROM" not in migration.upper()
