"""Regression tests for subscription activation audit records."""
from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.billing import Subscription
from app.models.enterprise import AuditLog
from app.routers import billing


class FakeQuery:
    def __init__(self, db):
        self.db = db

    def filter(self, *criteria):
        return self

    def first(self):
        return self.db.results.pop(0)


class FakeDB:
    def __init__(self, results, fail_at=None):
        self.results = list(results)
        self.fail_at = fail_at
        self.added = []
        self.rolled_back_rows = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def query(self, _model):
        return FakeQuery(self)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_count += 1
        if self.fail_at == "flush":
            raise IntegrityError("INSERT", {}, RuntimeError("unique payment id"))
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = uuid4()

    def commit(self):
        self.commit_count += 1
        if self.fail_at == "commit":
            raise IntegrityError("COMMIT", {}, RuntimeError("unique payment id"))

    def rollback(self):
        self.rollback_count += 1
        self.rolled_back_rows = list(self.added)
        self.added.clear()


class GatewayResource:
    def fetch(self, _identifier):
        return {}


class GatewayClient:
    def __init__(self, auth):
        self.auth = auth
        self.order = GatewayResource()
        self.payment = GatewayResource()


def _invoke(monkeypatch, db, org_id, payment_id="pay_audit_123"):
    client = GatewayClient(auth=("key_id", "key_secret"))
    monkeypatch.setitem(sys.modules, "razorpay", SimpleNamespace(Client=lambda auth: client))
    monkeypatch.setattr(billing.settings, "RAZORPAY_KEY_ID", "key_id")
    monkeypatch.setattr(billing.settings, "RAZORPAY_KEY_SECRET", "key_secret")
    monkeypatch.setattr(billing, "verify_payment_signature", lambda *_args: True)
    monkeypatch.setattr(billing, "validate_gateway_payment", lambda *_args: None)
    request = billing.VerifyPaymentRequest(
        org_id=str(org_id),
        plan="pro",
        razorpay_order_id="order_audit_123",
        razorpay_payment_id=payment_id,
        razorpay_signature="s" * 64,
    )
    return billing.verify_payment(
        request, org_id=str(org_id), db=db, _user=str(uuid4())
    )


def _audit_rows(rows):
    return [row for row in rows if isinstance(row, AuditLog)]


def test_new_subscription_activation_is_audited_without_payment_secrets(monkeypatch):
    org_id = uuid4()
    db = FakeDB([None, None])

    response = _invoke(monkeypatch, db, org_id)

    subscription_rows = [row for row in db.added if isinstance(row, Subscription)]
    audit_rows = _audit_rows(db.added)
    assert response["message"] == "Subscription activated: pro"
    assert len(subscription_rows) == 1
    assert len(audit_rows) == 1
    assert db.flush_count == 1
    assert db.commit_count == 1
    audit = audit_rows[0]
    assert audit.org_id == org_id
    assert audit.user_id is not None
    assert audit.action == "payment_verified"
    assert audit.entity_type == "subscription"
    assert audit.entity_id == str(subscription_rows[0].id)
    assert audit.changes["plan"] == {"before": None, "after": "pro"}
    assert audit.changes["status"] == {"before": None, "after": "active"}
    assert "razorpay_payment_id" not in repr(audit.changes)
    assert "razorpay_order_id" not in repr(audit.changes)


def test_existing_subscription_plan_change_is_audited_in_same_transaction(monkeypatch):
    org_id = uuid4()
    old_end = datetime(2026, 11, 30, tzinfo=timezone.utc)
    existing = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        plan="trial",
        status="active",
        current_period_end=old_end,
        razorpay_order_id=None,
        razorpay_payment_id=None,
    )
    db = FakeDB([None, existing])

    response = _invoke(monkeypatch, db, org_id)

    audit_rows = _audit_rows(db.added)
    assert response["message"] == "Subscription activated: pro"
    assert len(audit_rows) == 1
    assert db.commit_count == 1
    audit = audit_rows[0]
    assert audit.entity_id == str(existing.id)
    assert audit.changes["plan"] == {"before": "trial", "after": "pro"}
    assert audit.changes["current_period_end"]["before"] == old_end.isoformat()
    assert audit.changes["current_period_end"]["after"] is not None
    assert "status" not in audit.changes


def test_idempotent_payment_retry_does_not_create_another_audit_event(monkeypatch):
    org_id = uuid4()
    period_end = datetime(2026, 12, 8, tzinfo=timezone.utc)
    existing_payment = SimpleNamespace(
        org_id=org_id,
        razorpay_order_id="order_audit_123",
        plan="pro",
        current_period_end=period_end,
    )
    db = FakeDB([existing_payment])

    response = _invoke(monkeypatch, db, org_id)

    assert response["message"] == "Subscription already activated: pro"
    assert db.commit_count == 0
    assert db.added == []


@pytest.mark.parametrize("fail_at", ["flush", "commit"])
def test_payment_uniqueness_race_rolls_back_audit_record(monkeypatch, fail_at):
    org_id = uuid4()
    period_end = datetime(2026, 12, 8, tzinfo=timezone.utc)
    concurrent_payment = SimpleNamespace(
        org_id=org_id,
        razorpay_order_id="order_audit_123",
        plan="pro",
        current_period_end=period_end,
    )
    db = FakeDB([None, None, concurrent_payment], fail_at=fail_at)

    response = _invoke(monkeypatch, db, org_id)

    assert response["message"] == "Subscription already activated: pro"
    assert db.rollback_count == 1
    assert db.added == []
    if fail_at == "commit":
        assert _audit_rows(db.rolled_back_rows)
    else:
        assert not _audit_rows(db.rolled_back_rows)
