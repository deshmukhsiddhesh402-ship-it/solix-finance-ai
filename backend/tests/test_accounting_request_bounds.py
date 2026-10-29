"""Regression tests for bounded accounting calculation payloads."""
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.accounting import InventoryValuationRequest, TrialBalanceRequest


def test_trial_balance_request_rejects_more_than_500_lines():
    line = {
        "account_name": "Cash",
        "account_type": "asset",
        "debit": 1.0,
        "credit": 0.0,
    }
    with pytest.raises(ValidationError):
        TrialBalanceRequest(lines=[line] * 501)


def test_trial_balance_request_accepts_500_lines():
    line = {
        "account_name": "Cash",
        "account_type": "asset",
        "debit": 1.0,
        "credit": 0.0,
    }
    request = TrialBalanceRequest(lines=[line] * 500)
    assert len(request.lines) == 500


def test_inventory_valuation_rejects_more_than_1000_transactions():
    txn = {"txn_type": "purchase", "quantity": 1.0, "unit_cost": 10.0}
    with pytest.raises(ValidationError):
        InventoryValuationRequest(txns=[txn] * 1001, method="FIFO")


def test_inventory_valuation_accepts_1000_transactions():
    txn = {"txn_type": "purchase", "quantity": 1.0, "unit_cost": 10.0}
    request = InventoryValuationRequest(txns=[txn] * 1000, method="FIFO")
    assert len(request.txns) == 1000
