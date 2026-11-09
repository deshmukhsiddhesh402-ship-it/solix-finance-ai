import pytest

from app.services.billing_engine import PLANS, get_plan_limits, is_within_limit


def test_unknown_usage_key_fails_closed_instead_of_becoming_unlimited():
    with pytest.raises(ValueError, match="Unsupported usage key"):
        is_within_limit("pro", "unconfigured_feature_per_month", 0)


def test_only_explicit_unlimited_plan_limit_returns_true():
    assert PLANS["enterprise"]["limits"]["ai_chat_uploads_per_month"] is None
    assert is_within_limit("enterprise", "ai_chat_uploads_per_month", 10**9)


@pytest.mark.parametrize("usage", [True, False, -1, 1.5, "0", None])
def test_invalid_current_usage_is_rejected(usage):
    with pytest.raises(ValueError, match="non-negative integer"):
        is_within_limit("pro", "ai_chat_uploads_per_month", usage)


def test_plan_limit_copy_cannot_mutate_global_entitlements():
    limits = get_plan_limits("pro")
    limits["ai_chat_uploads_per_month"] = None

    assert PLANS["pro"]["limits"]["ai_chat_uploads_per_month"] == 200
    assert is_within_limit("pro", "ai_chat_uploads_per_month", 200) is False
