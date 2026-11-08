"""Regression tests for safe Razorpay order creation responses."""

from types import SimpleNamespace
from uuid import uuid4
import sys

import pytest
from fastapi import HTTPException

from app.routers import billing


def _invoke_create_order(monkeypatch, provider_result=None, provider_error=None):
    org_id = str(uuid4())

    def create_order(data):
        assert data["amount"] == 299900
        if provider_error is not None:
            raise provider_error
        return provider_result

    client = SimpleNamespace(order=SimpleNamespace(create=create_order))
    monkeypatch.setitem(sys.modules, "razorpay", SimpleNamespace(Client=lambda auth: client))
    monkeypatch.setattr(billing.settings, "RAZORPAY_KEY_ID", "key_id")
    monkeypatch.setattr(billing.settings, "RAZORPAY_KEY_SECRET", "key_secret")
    request = billing.CreateOrderRequest(org_id=org_id, plan="pro")
    return billing.create_order(request, org_id=org_id, db=object(), _user=str(uuid4()))


def test_create_order_returns_validated_provider_order(monkeypatch):
    result = _invoke_create_order(
        monkeypatch,
        provider_result={"id": "order_123", "amount": 299900, "currency": "INR"},
    )

    assert result == {
        "order_id": "order_123",
        "amount": 299900,
        "currency": "INR",
        "key_id": "key_id",
    }


def test_create_order_maps_provider_exception_to_generic_502(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _invoke_create_order(
            monkeypatch,
            provider_error=RuntimeError("provider credential or network detail"),
        )

    assert exc.value.status_code == 502
    assert exc.value.detail == "Payment order could not be created with the payment provider."
    assert "credential" not in exc.value.detail


@pytest.mark.parametrize(
    "provider_result",
    [
        None,
        [],
        {},
        {"id": "order_123", "amount": 1, "currency": "INR"},
        {"id": "order_123", "amount": 299900, "currency": "USD"},
        {"id": " order_123 ", "amount": 299900, "currency": "INR"},
        {"id": 123, "amount": 299900, "currency": "INR"},
        {"id": "order_123", "amount": True, "currency": "INR"},
    ],
)
def test_create_order_rejects_malformed_provider_order(monkeypatch, provider_result):
    with pytest.raises(HTTPException) as exc:
        _invoke_create_order(monkeypatch, provider_result=provider_result)

    assert exc.value.status_code == 502
    assert exc.value.detail == "Payment provider returned an invalid order response."
