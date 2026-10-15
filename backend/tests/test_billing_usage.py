"""Regression tests for atomic monthly subscription usage metering."""
from datetime import datetime, timezone

import pytest

from app.services.billing_engine import (
    _current_usage_period_start,
    check_and_consume_usage,
    release_usage,
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

    def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if sql.lstrip().startswith("SELECT plan"):
            return _Result(self.row)
        return _Result()

    def commit(self):
        self.commits += 1


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


def test_usage_period_start_is_first_day_of_utc_month():
    assert _current_usage_period_start(NOW) == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_trial_upload_consumes_one_unit_and_commits():
    db = _FakeDB(_row(count=4))
    result = check_and_consume_usage(db, ORG, "ai_chat_uploads_this_month", now=NOW)
    assert result == {
        "plan": "trial",
        "usage_key": "ai_chat_uploads_this_month",
        "current_usage": 5,
        "limit": 10,
        "allowed": True,
        "consumed": True,
    }
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


def test_release_usage_is_scoped_to_current_period():
    db = _FakeDB(_row())
    release_usage(db, ORG, "ai_chat_uploads_this_month", now=NOW)
    sql, params = db.statements[0]
    assert "GREATEST(ai_chat_uploads_this_month - 1, 0)" in sql
    assert "usage_period_start = :period_start" in sql
    assert params["period_start"] == _current_usage_period_start(NOW)
    assert db.commits == 1
