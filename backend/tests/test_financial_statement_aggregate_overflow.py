"""Regression tests for overflow-safe financial statement aggregation."""
from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.accounting_engine import build_balance_sheet, build_profit_and_loss


def _row(account_type, *, debit=0.0, credit=0.0):
    return {"type": account_type, "debit": debit, "credit": credit}


def test_profit_and_loss_rejects_income_aggregate_overflow():
    rows = [_row("income", credit=1e308), _row("income", credit=1e308)]
    with pytest.raises(ValueError, match="income total must remain finite"):
        build_profit_and_loss(rows)


def test_profit_and_loss_rejects_net_profit_overflow():
    rows = [_row("income", credit=1e308), _row("expense", credit=1e308)]
    with pytest.raises(ValueError, match="net profit must remain finite"):
        build_profit_and_loss(rows)


def test_balance_sheet_rejects_asset_aggregate_overflow():
    rows = [_row("asset", debit=1e308), _row("asset", debit=1e308)]
    with pytest.raises(ValueError, match="asset total must remain finite"):
        build_balance_sheet(rows, net_profit=0.0)


def test_balance_sheet_rejects_equity_plus_profit_overflow():
    rows = [_row("equity", credit=1e308)]
    with pytest.raises(ValueError, match="equity including current-year profit"):
        build_balance_sheet(rows, net_profit=1e308)


def test_balance_sheet_rejects_liabilities_and_equity_total_overflow():
    rows = [_row("liability", credit=1e308), _row("equity", credit=1e308)]
    with pytest.raises(ValueError, match="liabilities and equity total"):
        build_balance_sheet(rows, net_profit=0.0)


def test_balance_sheet_rejects_balance_difference_overflow():
    rows = [_row("asset", debit=1e308), _row("liability", debit=1e308)]
    with pytest.raises(ValueError, match="difference must remain finite"):
        build_balance_sheet(rows, net_profit=0.0)


def test_financial_statements_preserve_normal_finite_results():
    rows = [
        _row("asset", debit=150.0),
        _row("liability", credit=50.0),
        _row("equity", credit=80.0),
        _row("income", credit=40.0),
        _row("expense", debit=20.0),
    ]
    pnl = build_profit_and_loss(rows)
    sheet = build_balance_sheet(rows, net_profit=pnl["net_profit"])
    assert pnl == {"total_income": 40.0, "total_expense": 20.0, "net_profit": 20.0}
    assert sheet == {
        "total_assets": 150.0,
        "total_liabilities": 50.0,
        "total_equity": 100.0,
        "balances": True,
    }
