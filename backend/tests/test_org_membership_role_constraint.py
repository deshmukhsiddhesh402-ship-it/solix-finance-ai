"""Regression coverage for the organization-membership RBAC role constraint."""
from pathlib import Path
import re
import sys

from sqlalchemy import CheckConstraint

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import OrgMembership


_ALLOWED_ROLES = ("admin", "accountant", "auditor")


def _membership_table(sql: str) -> str:
    match = re.search(
        r"CREATE TABLE\s+org_memberships\s*\((.*?)\n\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_orm_membership_model_declares_the_supported_role_check():
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in OrgMembership.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_org_memberships_role" in checks
    normalized = checks["ck_org_memberships_role"].replace('"', "").casefold()
    assert all(role in normalized for role in _ALLOWED_ROLES)
    assert "role in" in normalized


def test_canonical_schema_restricts_membership_roles():
    schema = (ROOT_DIR / "database" / "schema.sql").read_text(encoding="utf-8")
    definition = _membership_table(schema)
    assert re.search(
        r"CONSTRAINT\s+ck_org_memberships_role\s+CHECK\s*"
        r"\(\s*role\s+IN\s*\('admin',\s*'accountant',\s*'auditor'\)\s*\)",
        definition,
        flags=re.IGNORECASE,
    )


def test_role_migration_rejects_unknown_values_before_adding_constraint():
    migration = (
        ROOT_DIR
        / "database"
        / "migrations"
        / "007_org_membership_role_check.sql"
    ).read_text(encoding="utf-8")
    preflight = migration.split("ALTER TABLE", 1)[0]

    assert re.search(
        r"FROM\s+org_memberships\s+WHERE\s+role\s+IS NULL\s+OR\s+role\s+NOT IN",
        preflight,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert preflight.count("RAISE EXCEPTION") == 1
    assert "ADD CONSTRAINT ck_org_memberships_role" in migration
    assert "UPDATE " not in migration.upper()
    assert "DELETE FROM" not in migration.upper()
