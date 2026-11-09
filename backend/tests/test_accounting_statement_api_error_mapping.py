"""API regression tests for accounting engine validation error mapping."""
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.accounting import (
    LedgerLineIn,
    TrialBalanceRequest,
    balance_sheet,
    create_journal_entry,
    profit_and_loss,
    trial_balance,
)


def _unbalanced_request():
    return TrialBalanceRequest(lines=[
        LedgerLineIn(account_name="Cash", account_type="asset", debit=100, credit=0),
        LedgerLineIn(account_name="Sales", account_type="income", debit=0, credit=90),
    ])


@pytest.mark.parametrize("endpoint", [profit_and_loss, balance_sheet])
def test_financial_statement_endpoints_map_unbalanced_engine_errors_to_422(endpoint):
    with pytest.raises(HTTPException) as exc:
        endpoint(_unbalanced_request())

    assert exc.value.status_code == 422
    assert "balanced trial-balance rows" in exc.value.detail


def test_trial_balance_endpoint_maps_engine_input_errors_to_422():
    request = TrialBalanceRequest(lines=[
        LedgerLineIn(account_name="   ", account_type="asset", debit=100, credit=0),
    ])

    with pytest.raises(HTTPException) as exc:
        trial_balance(request)

    assert exc.value.status_code == 422
    assert "Account name" in exc.value.detail


class _NoWriteDB:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


def test_journal_entry_maps_engine_input_errors_before_any_database_write():
    db = _NoWriteDB()
    org_id = str(uuid4())
    user_id = str(uuid4())
    lines = [
        LedgerLineIn(account_name="   ", account_type="asset", debit=100, credit=0),
        LedgerLineIn(account_name="Capital", account_type="equity", debit=0, credit=100),
    ]

    with pytest.raises(HTTPException) as exc:
        create_journal_entry(
            entry_date="2026-11-09",
            narration="Capital introduced",
            lines=lines,
            org_id=org_id,
            db=db,
            _user=user_id,
        )

    assert exc.value.status_code == 422
    assert "Account name" in exc.value.detail
    assert db.added == []


def test_valid_balanced_financial_statements_keep_existing_results():
    pnl = profit_and_loss(TrialBalanceRequest(lines=[
        LedgerLineIn(account_name="Cash", account_type="asset", debit=100, credit=0),
        LedgerLineIn(account_name="Sales", account_type="income", debit=0, credit=100),
    ]))
    sheet = balance_sheet(TrialBalanceRequest(lines=[
        LedgerLineIn(account_name="Cash", account_type="asset", debit=100, credit=0),
        LedgerLineIn(account_name="Capital", account_type="equity", debit=0, credit=100),
    ]))

    assert pnl["net_profit"] == 100
    assert sheet["balances"] is True
