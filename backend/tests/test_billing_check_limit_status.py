"""Regression tests for billing limit status consistency."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import billing


class FakeQuery:
    def __init__(self, subscription):
        self.subscription = subscription

    def filter(self, *_criteria):
        return self

    def first(self):
        return self.subscription


class FakeDB:
    def __init__(self, subscription):
        self.subscription = subscription

    def query(self, _model):
        return FakeQuery(self.subscription)


def _check_limit(subscription, usage=0):
    org_id = str(uuid4())
    if subscription is not None:
        subscription.ai_chat_uploads_this_month = usage
    return billing.check_limit(
        org_id=org_id,
        usage_key="ai_chat_uploads_this_month",
        db=FakeDB(subscription),
        _user=str(uuid4()),
    )


@pytest.mark.parametrize("status", ["past_due", "cancelled"])
def test_check_limit_denies_inactive_paid_subscriptions(status):
    subscription = SimpleNamespace(plan="pro", status=status)

    result = _check_limit(subscription)

    assert result["plan"] == "pro"
    assert result["status"] == status
    assert result["allowed"] is False


def test_check_limit_allows_active_paid_subscription_with_remaining_quota():
    subscription = SimpleNamespace(plan="pro", status="active")

    result = _check_limit(subscription, usage=199)

    assert result["status"] == "active"
    assert result["current_usage"] == 199
    assert result["allowed"] is True


def test_check_limit_denies_active_subscription_at_plan_limit():
    subscription = SimpleNamespace(plan="pro", status="active")

    result = _check_limit(subscription, usage=200)

    assert result["allowed"] is False


def test_check_limit_defaults_missing_subscription_to_active_trial():
    result = _check_limit(None)

    assert result["plan"] == "trial"
    assert result["status"] == "active"
    assert result["current_usage"] == 0
    assert result["allowed"] is True


def test_check_limit_rejects_unknown_usage_key():
    with pytest.raises(HTTPException) as exc:
        billing.check_limit(
            org_id=str(uuid4()),
            usage_key="unknown_counter",
            db=FakeDB(None),
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
