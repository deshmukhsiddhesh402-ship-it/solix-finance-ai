"""Regression coverage for allowed subscription plan and status values."""
from pathlib import Path
import re
import sys

from sqlalchemy import CheckConstraint

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.billing import Subscription
from app.services.billing_engine import PLANS


_ALLOWED_STATUSES = {"active", "past_due", "cancelled"}


def _subscription_table(sql: str) -> str:
    match = re.search(
        r"CREATE TABLE\s+subscriptions\s*\((.*?)\n\);",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def _check_constraints():
    return {
        constraint.name: str(constraint.sqltext)
        for constraint in Subscription.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_subscription_model_checks_match_supported_plan_and_status_values():
    checks = _check_constraints()
    assert "ck_subscriptions_plan" in checks
    assert "ck_subscriptions_status" in checks
    plan_values = set(re.findall(r"'([^']+)'", checks["ck_subscriptions_plan"]))
    status_values = set(re.findall(r"'([^']+)'", checks["ck_subscriptions_status"]))
    assert plan_values == set(PLANS)
    assert status_values == _ALLOWED_STATUSES


def test_canonical_schema_declares_subscription_plan_and_status_checks():
    schema = (ROOT_DIR / "database" / "schema.sql").read_text(encoding="utf-8")
    definition = _subscription_table(schema)
    assert "CONSTRAINT ck_subscriptions_plan" in definition
    assert "CONSTRAINT ck_subscriptions_status" in definition
    assert "plan IN ('trial', 'pro', 'enterprise')" in definition
    assert "status IN ('active', 'past_due', 'cancelled')" in definition


def test_subscription_migration_preflights_invalid_values_before_constraints():
    migration = (
        ROOT_DIR
        / "database"
        / "migrations"
        / "008_subscription_plan_status_checks.sql"
    ).read_text(encoding="utf-8")
    preflight = migration.split("ALTER TABLE", 1)[0]

    assert re.search(
        r"FROM\s+subscriptions\s+WHERE\s+plan\s+IS NULL\s+OR\s+plan\s+NOT IN",
        preflight,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert re.search(
        r"FROM\s+subscriptions\s+WHERE\s+status\s+IS NULL\s+OR\s+status\s+NOT IN",
        preflight,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert preflight.count("RAISE EXCEPTION") == 2
    assert migration.count("ADD CONSTRAINT") == 2
    assert "UPDATE " not in migration.upper()
    assert "DELETE FROM" not in migration.upper()
