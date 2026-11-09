"""Regression coverage for database-level tenant ownership constraints."""
from pathlib import Path
import re
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.billing import Subscription
from app.models.enterprise import ApiKey, OrgMembership, ScheduledReport


def _table_definition(sql: str, table: str) -> str:
    match = re.search(
        rf"CREATE TABLE\\s+{re.escape(table)}\\s*\\((.*?)\\n\\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None, f"missing CREATE TABLE for {table}"
    return match.group(1)


def test_orm_models_require_tenant_ownership_identifiers():
    assert OrgMembership.__table__.c.user_id.nullable is False
    assert OrgMembership.__table__.c.org_id.nullable is False
    assert ApiKey.__table__.c.org_id.nullable is False
    assert ScheduledReport.__table__.c.org_id.nullable is False
    assert Subscription.__table__.c.org_id.nullable is False


def test_canonical_schema_matches_non_nullable_tenant_ownership():
    schema = (ROOT_DIR / "database" / "schema.sql").read_text(encoding="utf-8")
    required_columns = {
        "org_memberships": ("user_id", "org_id"),
        "api_keys": ("org_id",),
        "scheduled_reports": ("org_id",),
        "subscriptions": ("org_id",),
    }

    for table, columns in required_columns.items():
        definition = _table_definition(schema, table)
        for column in columns:
            assert re.search(
                rf"^\\s*{column}\\s+UUID\\s+NOT NULL\\b",
                definition,
                flags=re.IGNORECASE | re.MULTILINE,
            ), f"{table}.{column} must be NOT NULL in schema.sql"


def test_migration_preflights_every_null_tenant_identifier_before_altering():
    migration = (
        ROOT_DIR
        / "database"
        / "migrations"
        / "005_enterprise_tenant_not_null.sql"
    ).read_text(encoding="utf-8")
    preflight = migration.split("ALTER TABLE", 1)[0]

    expected_preflights = {
        "org_memberships": r"user_id\\s+IS NULL\\s+OR\\s+org_id\\s+IS NULL",
        "api_keys": r"org_id\\s+IS NULL",
        "scheduled_reports": r"org_id\\s+IS NULL",
        "subscriptions": r"org_id\\s+IS NULL",
    }
    for table, predicate in expected_preflights.items():
        assert re.search(
            rf"FROM\\s+{table}\\s+WHERE\\s+{predicate}",
            preflight,
            flags=re.IGNORECASE | re.DOTALL,
        ), f"migration must preflight null ownership in {table}"

    assert preflight.count("RAISE EXCEPTION") == len(expected_preflights)
    assert migration.count("ALTER TABLE") == 5
    assert "DELETE FROM" not in migration.upper()
    assert "UPDATE " not in migration.upper()
