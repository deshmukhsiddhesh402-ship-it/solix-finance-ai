"""Request workload limits for compute-only accounting reports."""
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.accounting import TrialBalanceRequest


def _line(i=0):
    return {
        "account_name": f"Account {i}",
        "account_type": "asset",
        "debit": 100.0,
        "credit": 0.0,
    }


def test_trial_balance_request_rejects_empty_lines():
    with pytest.raises(ValidationError):
        TrialBalanceRequest(lines=[])


def test_trial_balance_request_rejects_more_than_500_lines():
    with pytest.raises(ValidationError):
        TrialBalanceRequest(lines=[_line(i) for i in range(501)])


def test_trial_balance_request_accepts_maximum_500_lines():
    req = TrialBalanceRequest(lines=[_line(i) for i in range(500)])
    assert len(req.lines) == 500
