"""Regression tests for direct trial-balance numeric validation and overflow."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.accounting_engine import LedgerLine, build_trial_balance


@pytest.mark.parametrize("amount", [True, False, "100", None, 10**1000, float("nan"), float("inf"), float("-inf")])
def test_trial_balance_rejects_non_numeric_or_non_finite_amounts(amount):
    with pytest.raises(ValueError, match="finite numbers"):
        build_trial_balance([LedgerLine("Cash", "asset", debit=amount, credit=0)])


@pytest.mark.parametrize("amount", [-1, -0.01])
def test_trial_balance_rejects_negative_amounts(amount):
    with pytest.raises(ValueError, match="cannot be negative"):
        build_trial_balance([LedgerLine("Cash", "asset", debit=amount, credit=0)])


def test_trial_balance_rejects_per_account_aggregation_overflow():
    lines = [
        LedgerLine("Cash", "asset", debit=1e308, credit=0),
        LedgerLine("Cash", "asset", debit=1e308, credit=0),
    ]
    with pytest.raises(ValueError, match="Aggregated"):
        build_trial_balance(lines)


def test_trial_balance_rejects_cross_account_total_overflow():
    lines = [
        LedgerLine("Cash", "asset", debit=1e308, credit=0),
        LedgerLine("Receivables", "asset", debit=1e308, credit=0),
    ]
    with pytest.raises(ValueError, match="totals must remain finite"):
        build_trial_balance(lines)


def test_trial_balance_still_accepts_balanced_finite_amounts():
    result = build_trial_balance([
        LedgerLine("Cash", "asset", debit=1000.0, credit=0.0),
        LedgerLine("Capital", "equity", debit=0.0, credit=1000.0),
    ])
    assert result["is_balanced"] is True
    assert result["total_debit"] == 1000.0
    assert result["total_credit"] == 1000.0


@pytest.mark.parametrize("account_name", [None, 123, [], {}])
def test_trial_balance_rejects_malformed_account_names(account_name):
    with pytest.raises(ValueError, match="Account name"):
        build_trial_balance([LedgerLine(account_name, "asset", debit=1, credit=0)])


def test_trial_balance_rejects_unhashable_account_type():
    with pytest.raises(ValueError, match="Invalid account type"):
        build_trial_balance([LedgerLine("Cash", [], debit=1, credit=0)])


@pytest.mark.parametrize("rows", [None, {}, "invalid"])
def test_financial_statement_engine_rejects_non_list_trial_balance_rows(rows):
    from app.services.accounting_engine import build_profit_and_loss

    with pytest.raises(ValueError, match="must be a list"):
        build_profit_and_loss(rows)
