"""Regression tests for balanced financial-statement inputs and request bounds."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.accounting import (
    LedgerLineIn,
    TrialBalanceRequest,
    balance_sheet,
    profit_and_loss,
)


def _line(name: str, account_type: str, *, debit: float = 0, credit: float = 0):
    return LedgerLineIn(
        account_name=name,
        account_type=account_type,
        debit=debit,
        credit=credit,
    )


def test_profit_and_loss_rejects_unbalanced_entries():
    req = TrialBalanceRequest(lines=[
        _line("Cash", "asset", debit=100),
        _line("Sales", "income", credit=90),
    ])

    with pytest.raises(HTTPException) as exc:
        profit_and_loss(req)

    assert exc.value.status_code == 422
    assert "do not balance" in exc.value.detail


def test_balance_sheet_rejects_unbalanced_entries():
    req = TrialBalanceRequest(lines=[
        _line("Cash", "asset", debit=100),
        _line("Capital", "equity", credit=90),
    ])

    with pytest.raises(HTTPException) as exc:
        balance_sheet(req)

    assert exc.value.status_code == 422
    assert "do not balance" in exc.value.detail


def test_profit_and_loss_accepts_balanced_entries():
    req = TrialBalanceRequest(lines=[
        _line("Cash", "asset", debit=100),
        _line("Sales", "income", credit=100),
    ])

    result = profit_and_loss(req)

    assert result["total_income"] == 100
    assert result["total_expense"] == 0
    assert result["net_profit"] == 100


def test_balance_sheet_accepts_balanced_entries():
    req = TrialBalanceRequest(lines=[
        _line("Cash", "asset", debit=100),
        _line("Capital", "equity", credit=100),
    ])

    result = balance_sheet(req)

    assert result["total_assets"] == 100
    assert result["balances"] is True


def test_trial_balance_request_requires_two_to_500_lines():
    with pytest.raises(ValidationError):
        TrialBalanceRequest(lines=[_line("Cash", "asset", debit=100)])

    lines = [_line(f"Expense {i}", "expense", debit=1) for i in range(500)]
    lines.append(_line("Capital", "equity", credit=500))
    with pytest.raises(ValidationError):
        TrialBalanceRequest(lines=lines)
