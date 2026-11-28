from types import SimpleNamespace
import pytest

from app.services.billing_engine import consume_usage


def test_consume_usage_increments_within_plan_limit():
    subscription = SimpleNamespace(plan="trial", ai_chat_uploads_this_month=9)
    consume_usage(subscription, "ai_chat_uploads_this_month")
    assert subscription.ai_chat_uploads_this_month == 10


def test_consume_usage_rejects_at_plan_limit():
    subscription = SimpleNamespace(plan="trial", invoice_ocr_this_month=20)
    with pytest.raises(ValueError, match="Monthly limit reached"):
        consume_usage(subscription, "invoice_ocr_this_month")
    assert subscription.invoice_ocr_this_month == 20


def test_consume_usage_treats_missing_counter_as_zero():
    subscription = SimpleNamespace(plan="enterprise", ai_chat_uploads_this_month=None)
    consume_usage(subscription, "ai_chat_uploads_this_month")
    assert subscription.ai_chat_uploads_this_month == 1
