import pytest

from app.services.accounting_engine import LedgerLine, build_trial_balance


@pytest.mark.parametrize("value", [True, False, "100", None, float("nan"), float("inf"), -float("inf")])
def test_trial_balance_rejects_invalid_debit_amounts(value):
    with pytest.raises(ValueError):
        build_trial_balance([LedgerLine("Cash", "asset", debit=value, credit=0)])


@pytest.mark.parametrize("value", [True, False, "100", None, float("nan"), float("inf"), -float("inf")])
def test_trial_balance_rejects_invalid_credit_amounts(value):
    with pytest.raises(ValueError):
        build_trial_balance([LedgerLine("Capital", "equity", debit=0, credit=value)])


def test_trial_balance_rejects_integer_too_large_for_float_conversion():
    with pytest.raises(ValueError):
        build_trial_balance([LedgerLine("Cash", "asset", debit=10**10000, credit=0)])


def test_trial_balance_preserves_valid_balanced_entries():
    result = build_trial_balance([
        LedgerLine("Cash", "asset", debit=1000, credit=0),
        LedgerLine("Capital", "equity", debit=0, credit=1000),
    ])
    assert result["is_balanced"] is True
    assert result["total_debit"] == 1000.0
    assert result["total_credit"] == 1000.0
