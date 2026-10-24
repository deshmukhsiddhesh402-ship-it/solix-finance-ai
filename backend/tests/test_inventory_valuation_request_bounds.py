"""Regression tests for inventory valuation request bounds."""
import os
import sys

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.accounting import InventoryValuationRequest


def _txn(i=0):
    return {
        "txn_type": "purchase",
        "quantity": 1.0,
        "unit_cost": float(i + 1),
    }


def test_inventory_valuation_rejects_empty_transactions():
    with pytest.raises(ValidationError):
        InventoryValuationRequest(txns=[], method="FIFO")


def test_inventory_valuation_rejects_more_than_1000_transactions():
    with pytest.raises(ValidationError):
        InventoryValuationRequest(txns=[_txn(i) for i in range(1001)], method="FIFO")


def test_inventory_valuation_accepts_maximum_1000_transactions():
    req = InventoryValuationRequest(txns=[_txn(i) for i in range(1000)], method="FIFO")
    assert len(req.txns) == 1000
