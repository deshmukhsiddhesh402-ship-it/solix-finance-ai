"""Regression tests for failed-payment webhook state transitions and audit events."""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.billing import Subscription
from app.models.enterprise import AuditLog
from app.routers import billing


class FakeRequest:
    def __init__(self, payload):
        self.headers = {"X-Razorpay-Signature": "verified-signature"}
        self.body_bytes = json.dumps(payload).encode("utf-8")

    async def stream(self):
        yield self.body_bytes


class FakeQuery:
    def __init__(self, row):
        self.row = row
        self.lock_requested = False

    def filter(self, *criteria):
        return self

    def with_for_update(self):
        self.lock_requested = True
        return self

    def first(self):
        return self.row


class FakeDB:
    def __init__(self, subscription):
        self.subscription = subscription
        self.query_obj = None
        self.added = []
        self.commit_count = 0

    def query(self, model):
        assert model is Subscription
        self.query_obj = FakeQuery(self.subscription)
        return self.query_obj

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commit_count += 1


def _payload(org_id, order_id="order_failed_123"):
    return {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "notes": {"org_id": str(org_id)},
                    "order_id": order_id,
                }
            }
        },
    }


def _run(monkeypatch, db, payload):
    monkeypatch.setattr(billing.settings, "RAZORPAY_WEBHOOK_SECRET", "configured-secret")
    monkeypatch.setattr(billing, "verify_webhook_signature", lambda *_args: True)
    return asyncio.run(billing.razorpay_webhook(FakeRequest(payload), db=db))


def _audit_rows(db):
    return [row for row in db.added if isinstance(row, AuditLog)]


def test_failed_payment_transition_is_audited_and_row_locked(monkeypatch):
    org_id = uuid4()
    subscription = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        razorpay_order_id="order_failed_123",
        razorpay_payment_id=None,
        status="active",
    )
    db = FakeDB(subscription)

    response = _run(monkeypatch, db, _payload(org_id))

    assert response == {"status": "ok"}
    assert subscription.status == "past_due"
    assert db.query_obj.lock_requested is True
    assert db.commit_count == 1
    assert len(_audit_rows(db)) == 1
    audit = _audit_rows(db)[0]
    assert audit.org_id == org_id
    assert audit.user_id is None
    assert audit.action == "payment_failed"
    assert audit.entity_type == "subscription"
    assert audit.entity_id == str(subscription.id)
    assert audit.changes == {"status": {"before": "active", "after": "past_due"}}


def test_cancelled_subscription_is_not_resurrected_by_late_failure(monkeypatch):
    org_id = uuid4()
    subscription = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        razorpay_order_id="order_failed_123",
        razorpay_payment_id=None,
        status="cancelled",
    )
    db = FakeDB(subscription)

    _run(monkeypatch, db, _payload(org_id))

    assert subscription.status == "cancelled"
    assert db.commit_count == 0
    assert _audit_rows(db) == []


def test_repeated_failed_payment_delivery_does_not_duplicate_audit(monkeypatch):
    org_id = uuid4()
    subscription = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        razorpay_order_id="order_failed_123",
        razorpay_payment_id=None,
        status="past_due",
    )
    db = FakeDB(subscription)

    _run(monkeypatch, db, _payload(org_id))

    assert subscription.status == "past_due"
    assert db.commit_count == 0
    assert _audit_rows(db) == []


def test_failed_payment_does_not_downgrade_subscription_with_verified_payment(monkeypatch):
    org_id = uuid4()
    subscription = SimpleNamespace(
        id=uuid4(),
        org_id=org_id,
        razorpay_order_id="order_failed_123",
        razorpay_payment_id="pay_successful_123",
        status="active",
    )
    db = FakeDB(subscription)

    _run(monkeypatch, db, _payload(org_id))

    assert subscription.status == "active"
    assert db.commit_count == 0
    assert _audit_rows(db) == []


def test_invalid_tenant_note_does_not_query_or_change_subscriptions(monkeypatch):
    subscription = SimpleNamespace(
        id=uuid4(),
        org_id=uuid4(),
        razorpay_order_id="order_failed_123",
        razorpay_payment_id=None,
        status="active",
    )
    db = FakeDB(subscription)
    payload = _payload("not-a-uuid")

    _run(monkeypatch, db, payload)

    assert subscription.status == "active"
    assert db.query_obj is None
    assert db.commit_count == 0
    assert _audit_rows(db) == []
