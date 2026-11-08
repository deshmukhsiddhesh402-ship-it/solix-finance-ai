from datetime import datetime, timezone
from types import SimpleNamespace
import sys
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.routers import billing


class _Query:
    def __init__(self, db):
        self.db = db

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.db.first_results.pop(0)


class _Database:
    def __init__(self, first_results):
        self.first_results = list(first_results)
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, _model):
        return _Query(self)

    def add(self, value):
        self.added.append(value)

    def flush(self):
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid.uuid4()

    def commit(self):
        self.commits += 1
        raise IntegrityError("INSERT", {}, RuntimeError("unique payment id"))

    def rollback(self):
        self.rollbacks += 1


class _GatewayResource:
    def fetch(self, _identifier):
        return {}


class _GatewayClient:
    def __init__(self, auth):
        self.auth = auth
        self.order = _GatewayResource()
        self.payment = _GatewayResource()


def _invoke_verify_payment(monkeypatch, db, org_id, order_id="order_123", payment_id="pay_123"):
    client = _GatewayClient(auth=("key_id", "key_secret"))
    monkeypatch.setitem(sys.modules, "razorpay", SimpleNamespace(Client=lambda auth: client))
    monkeypatch.setattr(billing.settings, "RAZORPAY_KEY_ID", "key_id")
    monkeypatch.setattr(billing.settings, "RAZORPAY_KEY_SECRET", "key_secret")
    monkeypatch.setattr(billing, "verify_payment_signature", lambda *_args: True)
    monkeypatch.setattr(billing, "validate_gateway_payment", lambda *_args: None)

    request = billing.VerifyPaymentRequest(
        org_id=str(org_id),
        plan="pro",
        razorpay_order_id=order_id,
        razorpay_payment_id=payment_id,
        razorpay_signature="s" * 64,
    )
    return billing.verify_payment(request, org_id=str(org_id), db=db, _user=str(uuid.uuid4()))


def test_concurrent_exact_payment_retry_is_idempotent_after_unique_conflict(monkeypatch):
    org_id = uuid.uuid4()
    period_end = datetime(2026, 12, 4, tzinfo=timezone.utc)
    existing = SimpleNamespace(
        org_id=org_id,
        razorpay_order_id="order_123",
        plan="pro",
        current_period_end=period_end,
    )
    db = _Database([None, None, existing])

    response = _invoke_verify_payment(monkeypatch, db, org_id)

    assert response == {
        "message": "Subscription already activated: pro",
        "current_period_end": period_end.isoformat(),
    }
    assert db.commits == 1
    assert db.rollbacks == 1


@pytest.mark.parametrize(
    "existing, expected_detail",
    [
        (
            SimpleNamespace(
                org_id=uuid.uuid4(),
                razorpay_order_id="order_123",
                plan="pro",
                current_period_end=None,
            ),
            "Subscription or payment has already been recorded.",
        ),
        (
            SimpleNamespace(
                org_id=None,
                razorpay_order_id="different_order",
                plan="pro",
                current_period_end=None,
            ),
            "Subscription or payment has already been recorded.",
        ),
        (
            SimpleNamespace(
                org_id=None,
                razorpay_order_id="order_123",
                plan="enterprise",
                current_period_end=None,
            ),
            "Subscription or payment has already been recorded.",
        ),
    ],
)
def test_concurrent_payment_conflict_returns_409(monkeypatch, existing, expected_detail):
    org_id = uuid.uuid4()
    db = _Database([None, None, existing])

    with pytest.raises(HTTPException) as exc:
        _invoke_verify_payment(monkeypatch, db, org_id)

    assert exc.value.status_code == 409
    assert exc.value.detail == expected_detail
    assert db.commits == 1
    assert db.rollbacks == 1


def test_unique_conflict_without_matching_payment_record_returns_409(monkeypatch):
    org_id = uuid.uuid4()
    db = _Database([None, None, None])

    with pytest.raises(HTTPException) as exc:
        _invoke_verify_payment(monkeypatch, db, org_id)

    assert exc.value.status_code == 409
    assert exc.value.detail == "Subscription or payment has already been recorded."
    assert db.commits == 1
    assert db.rollbacks == 1
