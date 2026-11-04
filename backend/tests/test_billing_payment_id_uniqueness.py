from pathlib import Path

from app.models.billing import Subscription


def test_razorpay_payment_identifier_has_database_unique_constraint():
    payment_id = Subscription.__table__.c.razorpay_payment_id

    assert payment_id.unique is True
    assert payment_id.nullable is True


def test_payment_id_migration_preflights_duplicates_before_creating_index():
    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "004_unique_razorpay_payment_id.sql"
    )
    sql = migration.read_text(encoding="utf-8")

    assert "HAVING COUNT(*) > 1" in sql
    assert "RAISE EXCEPTION" in sql
    assert "END;\n$$;" in sql
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_subscriptions_razorpay_payment_id" in sql
    assert "WHERE razorpay_payment_id IS NOT NULL" in sql
