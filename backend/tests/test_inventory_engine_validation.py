"""Regression tests for direct inventory-engine input bounds."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.accounting_engine import InventoryTxn, inventory_valuation


def test_inventory_engine_accepts_valid_transactions():
    result = inventory_valuation([InventoryTxn("purchase", 2, 50)], "FIFO")
    assert result["closing_quantity"] == 2
    assert result["closing_inventory_value"] == 100


def test_inventory_engine_rejects_non_list_and_oversized_inputs():
    with pytest.raises(ValueError, match="must be a list"):
        inventory_valuation((), "FIFO")
    with pytest.raises(ValueError, match="limited to 1000"):
        inventory_valuation([InventoryTxn("purchase", 1, 1)] * 1001, "FIFO")


@pytest.mark.parametrize(
    "txn",
    [
        object(),
        InventoryTxn("purchase", True, 100),
        InventoryTxn("purchase", 1, float("nan")),
        InventoryTxn("purchase", 1, float("inf")),
    ],
)
def test_inventory_engine_rejects_invalid_transaction_objects_and_amounts(txn):
    with pytest.raises(ValueError):
        inventory_valuation([txn], "FIFO")


def test_inventory_engine_rejects_invalid_valuation_method():
    with pytest.raises(ValueError, match="Unsupported"):
        inventory_valuation([InventoryTxn("purchase", 1, 10)], "UNKNOWN")
