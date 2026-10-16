"""PostgreSQL integration tests for quota locking and idempotent compensation.

These tests use an isolated schema and never connect to a production database.
Set TEST_DATABASE_URL to enable them; CI provisions a disposable PostgreSQL service.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.billing_engine import check_and_consume_usage, release_usage


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def pg_engine():
    schema = "billing_test_" + uuid.uuid4().hex
    admin_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    with admin_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        with test_engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE organizations (
                    id UUID PRIMARY KEY
                )
            """))
            conn.execute(text("""
                CREATE TABLE subscriptions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    org_id UUID NOT NULL UNIQUE REFERENCES organizations(id),
                    plan VARCHAR(20) NOT NULL DEFAULT 'trial',
                    status VARCHAR(20) NOT NULL DEFAULT 'active',
                    current_period_end TIMESTAMPTZ,
                    ai_chat_uploads_this_month INTEGER NOT NULL DEFAULT 0,
                    invoice_ocr_this_month INTEGER NOT NULL DEFAULT 0,
                    usage_period_start TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            migration_path = (
                Path(__file__).resolve().parents[2]
                / "database" / "migrations" / "006_subscription_usage_reservations.sql"
            )
            conn.exec_driver_sql(migration_path.read_text(encoding="utf-8"))
        yield test_engine
    finally:
        test_engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed_org(engine, *, count=0):
    org_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO organizations (id) VALUES (:org_id)"),
            {"org_id": org_id},
        )
        conn.execute(text("""
            INSERT INTO subscriptions (
                org_id, plan, status, current_period_end,
                ai_chat_uploads_this_month, invoice_ocr_this_month,
                usage_period_start
            ) VALUES (
                :org_id, 'trial', 'active', :period_end,
                :count, 0, :period_start
            )
        """), {
            "org_id": org_id,
            "period_end": datetime(2026, 11, 14, tzinfo=timezone.utc),
            "count": count,
            "period_start": datetime(2026, 10, 1, tzinfo=timezone.utc),
        })
    return org_id


def test_postgres_concurrent_requests_cannot_exceed_trial_limit(pg_engine):
    org_id = _seed_org(pg_engine, count=9)
    barrier = __import__("threading").Barrier(2)

    def attempt():
        with Session(pg_engine) as db:
            barrier.wait(timeout=10)
            return check_and_consume_usage(
                db, org_id, "ai_chat_uploads_this_month", now=NOW
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    assert sum(result["allowed"] for result in results) == 1
    assert sum(result["consumed"] for result in results) == 1
    with pg_engine.connect() as conn:
        count = conn.execute(text(
            "SELECT ai_chat_uploads_this_month FROM subscriptions WHERE org_id = :org_id"
        ), {"org_id": org_id}).scalar_one()
        reservations = conn.execute(text(
            "SELECT count(*) FROM subscription_usage_reservations WHERE org_id = :org_id"
        ), {"org_id": org_id}).scalar_one()
    assert count == 10
    assert reservations == 1


def test_postgres_duplicate_release_only_decrements_once(pg_engine):
    org_id = _seed_org(pg_engine)
    with Session(pg_engine) as db:
        first = check_and_consume_usage(
            db, org_id, "ai_chat_uploads_this_month", now=NOW
        )
    with Session(pg_engine) as db:
        second = check_and_consume_usage(
            db, org_id, "ai_chat_uploads_this_month", now=NOW
        )
    assert first["reservation_id"] != second["reservation_id"]

    with Session(pg_engine) as db:
        release_usage(
            db, org_id, "ai_chat_uploads_this_month", first["reservation_id"], now=NOW
        )
    with Session(pg_engine) as db:
        release_usage(
            db, org_id, "ai_chat_uploads_this_month", first["reservation_id"], now=NOW
        )

    with pg_engine.connect() as conn:
        count = conn.execute(text(
            "SELECT ai_chat_uploads_this_month FROM subscriptions WHERE org_id = :org_id"
        ), {"org_id": org_id}).scalar_one()
        states = conn.execute(text("""
            SELECT id, released_at FROM subscription_usage_reservations
            WHERE org_id = :org_id ORDER BY id
        """), {"org_id": org_id}).all()
    assert count == 1
    released = {str(row.id): row.released_at for row in states}
    assert released[first["reservation_id"]] is not None
    assert released[second["reservation_id"]] is None
