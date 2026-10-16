"""Regression tests for atomic monthly subscription usage metering."""
from datetime import datetime, timezone

import pytest

from app.services.billing_engine import (
    _current_usage_period_start,
    check_and_consume_usage,
    release_usage,
    release_usage_after_failure,
)


class _Result:
    def __init__(self, row=None):
        self.row = row

    def mappings(self):
        return self

    def one(self):
        return self.row


class _FakeDB:
    def __init__(self, row):
        self.row = row
        self.statements = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if sql.lstrip().startswith("SELECT plan"):
            return _Result(self.row)
        return _Result()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)
ORG = "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"


def _row(plan="trial", count=0, period=None):
    return {
        "plan": plan,
        "status": "active",
        "current_period_end": datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc),
        "usage_period_start": period or _current_usage_period_start(NOW),
        "ai_chat_uploads_this_month": count,
        "invoice_ocr_this_month": count,
    }


def test_subscription_usage_period_default_is_timezone_independent():
    from app.models.billing import Subscription

    default_sql = str(Subscription.__table__.c.usage_period_start.server_default.arg)
    assert "date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'" in default_sql


def test_usage_period_start_is_first_day_of_utc_month():
    assert _current_usage_period_start(NOW) == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_trial_upload_consumes_one_unit_and_commits():
    db = _FakeDB(_row(count=4))
    result = check_and_consume_usage(db, ORG, "ai_chat_uploads_this_month", now=NOW)
    assert result["plan"] == "trial"
    assert result["usage_key"] == "ai_chat_uploads_this_month"
    assert result["current_usage"] == 5
    assert result["limit"] == 10
    assert result["allowed"] is True
    assert result["consumed"] is True
    assert result["reservation_id"]
    assert any("FOR UPDATE" in sql for sql, _ in db.statements)
    assert db.commits == 1


def test_trial_limit_blocks_consumption():
    db = _FakeDB(_row(count=10))
    result = check_and_consume_usage(db, ORG, "ai_chat_uploads_this_month", now=NOW)
    assert result["allowed"] is False
    assert result["consumed"] is False
    assert result["current_usage"] == 10
    assert not any("SET ai_chat_uploads_this_month = :current_usage" in sql for sql, _ in db.statements)


def test_check_only_does_not_consume_usage():
    db = _FakeDB(_row(count=3))
    result = check_and_consume_usage(
        db, ORG, "invoice_ocr_this_month", consume=False, now=NOW
    )
    assert result["allowed"] is True
    assert result["current_usage"] == 3
    assert result["consumed"] is False
    assert result["reservation_id"] is None
    assert not any("SET invoice_ocr_this_month = :current_usage" in sql for sql, _ in db.statements)


def test_stale_usage_period_resets_before_limit_check():
    old_period = datetime(2026, 9, 1, tzinfo=timezone.utc)
    db = _FakeDB(_row(count=10, period=old_period))
    result = check_and_consume_usage(
        db, ORG, "ai_chat_uploads_this_month", consume=False, now=NOW
    )
    assert result["allowed"] is True
    assert result["current_usage"] == 0
    assert any("SET ai_chat_uploads_this_month = 0" in sql for sql, _ in db.statements)
    assert any("invoice_ocr_this_month = 0" in sql for sql, _ in db.statements)


def test_future_usage_period_resets_instead_of_preserving_stale_counters():
    future_period = datetime(2026, 11, 1, tzinfo=timezone.utc)
    db = _FakeDB(_row(count=10, period=future_period))
    result = check_and_consume_usage(
        db, ORG, "ai_chat_uploads_this_month", consume=False, now=NOW
    )
    assert result["allowed"] is True
    assert result["current_usage"] == 0
    assert any("usage_period_start = :period_start" in sql for sql, _ in db.statements)


def test_enterprise_plan_is_unlimited():
    db = _FakeDB(_row(plan="enterprise", count=9000))
    result = check_and_consume_usage(db, ORG, "invoice_ocr_this_month", now=NOW)
    assert result["allowed"] is True
    assert result["current_usage"] == 9001
    assert result["limit"] is None


def test_expired_paid_plan_falls_back_to_trial_quota():
    db = _FakeDB({
        **_row(plan="pro", count=10),
        "current_period_end": datetime(2026, 10, 1, tzinfo=timezone.utc),
    })
    result = check_and_consume_usage(db, ORG, "ai_chat_uploads_this_month", now=NOW)
    assert result["plan"] == "trial"
    assert result["allowed"] is False
    assert result["current_usage"] == 10


def test_cancelled_paid_plan_falls_back_to_trial_quota():
    row = _row(plan="enterprise", count=10)
    row["status"] = "cancelled"
    db = _FakeDB(row)
    result = check_and_consume_usage(db, ORG, "ai_chat_uploads_this_month", now=NOW)
    assert result["plan"] == "trial"
    assert result["allowed"] is False


def test_unknown_usage_key_fails_closed():
    db = _FakeDB(_row())
    with pytest.raises(ValueError, match="Unsupported usage key"):
        check_and_consume_usage(db, ORG, "arbitrary_column", now=NOW)
    assert db.statements == []


def test_release_usage_is_idempotent_and_scoped_to_reservation_and_period():
    db = _FakeDB(_row())
    reservation_id = "4b5d66c0-5d66-4c0b-b2c5-7cbbd4a8ad01"
    release_usage(db, ORG, "ai_chat_uploads_this_month", reservation_id, now=NOW)
    sql, params = db.statements[0]
    assert "WITH released AS" in sql
    assert "released_at IS NULL" in sql
    assert "id = :reservation_id" in sql
    assert "GREATEST(ai_chat_uploads_this_month - 1, 0)" in sql
    assert "usage_period_start = :period_start" in sql
    assert params["reservation_id"] == reservation_id
    assert params["period_start"] == _current_usage_period_start(NOW)
    assert db.commits == 1

def test_failed_quota_compensation_is_logged_without_masking_error(caplog, monkeypatch):
    def fail_release(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("app.services.billing_engine.release_usage", fail_release)
    db = _FakeDB(_row())
    with caplog.at_level("ERROR", logger="app.services.billing_engine"):
        released = release_usage_after_failure(db, ORG, "ai_chat_uploads_this_month", "4b5d66c0-5d66-4c0b-b2c5-7cbbd4a8ad01", now=NOW)

    assert released is False
    assert db.rollbacks == 1
    assert "Failed to release reserved ai_chat_uploads_this_month usage" in caplog.text
    assert "database unavailable" in caplog.text


def test_usage_period_start_normalizes_naive_datetime_as_utc():
    naive_now = datetime(2026, 10, 15, 12, 34, 56)
    assert _current_usage_period_start(naive_now) == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_usage_period_start_normalizes_non_utc_offset():
    from datetime import timedelta

    plus_five_thirty = timezone(timedelta(hours=5, minutes=30))
    local_now = datetime(2026, 10, 1, 2, 0, tzinfo=plus_five_thirty)
    # This instant is still in September in UTC, so the period anchor must be
    # September 1 rather than October 1 based on the caller's local calendar.
    assert _current_usage_period_start(local_now) == datetime(2026, 9, 1, tzinfo=timezone.utc)

@pytest.mark.parametrize("usage_key", ["arbitrary_column", "", "users"])
def test_release_usage_rejects_unsupported_key_before_database_access(usage_key):
    db = _FakeDB(_row())
    with pytest.raises(ValueError, match="Unsupported usage key"):
        release_usage(db, ORG, usage_key, "4b5d66c0-5d66-4c0b-b2c5-7cbbd4a8ad01", now=NOW)
    assert db.statements == []
    assert db.commits == 0


def test_release_usage_requires_reservation_id_before_database_access():
    db = _FakeDB(_row())
    with pytest.raises(ValueError, match="reservation ID is required"):
        release_usage(db, ORG, "ai_chat_uploads_this_month", "", now=NOW)
    assert db.statements == []
    assert db.commits == 0


def test_consumption_persists_a_unique_reservation_in_the_same_transaction():
    db = _FakeDB(_row())
    result = check_and_consume_usage(db, ORG, "ai_chat_uploads_this_month", now=NOW)
    assert result["reservation_id"]
    assert any("INSERT INTO subscription_usage_reservations" in sql for sql, _ in db.statements)
    assert db.commits == 1
