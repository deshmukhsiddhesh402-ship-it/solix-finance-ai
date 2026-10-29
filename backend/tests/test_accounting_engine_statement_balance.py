"""Pure-engine regression tests for balanced financial statements."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.accounting_engine import build_balance_sheet, build_profit_and_loss


def test_profit_and_loss_rejects_unbalanced_trial_balance_rows():
    rows = [
        {"account": "Cash", "type": "asset", "debit": 100, "credit": 0},
        {"account": "Sales", "type": "income", "debit": 0, "credit": 90},
    ]
    with pytest.raises(ValueError, match="require balanced"):
        build_profit_and_loss(rows)


def test_balance_sheet_rejects_unbalanced_trial_balance_rows():
    rows = [
        {"account": "Cash", "type": "asset", "debit": 100, "credit": 0},
        {"account": "Capital", "type": "equity", "debit": 0, "credit": 90},
    ]
    with pytest.raises(ValueError, match="require balanced"):
        build_balance_sheet(rows, 0)


def test_balanced_trial_balance_rows_still_produce_statements():
    pnl_rows = [
        {"account": "Cash", "type": "asset", "debit": 100, "credit": 0},
        {"account": "Sales", "type": "income", "debit": 0, "credit": 100},
    ]
    balance_rows = [
        {"account": "Cash", "type": "asset", "debit": 100, "credit": 0},
        {"account": "Capital", "type": "equity", "debit": 0, "credit": 100},
    ]

    assert build_profit_and_loss(pnl_rows)["net_profit"] == 100
    assert build_balance_sheet(balance_rows, 0)["balances"] is True
