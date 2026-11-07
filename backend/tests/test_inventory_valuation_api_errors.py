"""API regression tests for inventory valuation validation errors."""
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.accounting import InventoryValuationRequest, inventory_valuation_endpoint


def test_inventory_endpoint_maps_insufficient_stock_to_http_422():
    request = InventoryValuationRequest(
        txns=[{"txn_type": "sale", "quantity": 1, "unit_cost": 0}],
        method="FIFO",
    )

    with pytest.raises(HTTPException) as exc:
        inventory_valuation_endpoint(request)

    assert exc.value.status_code == 422
    assert "exceeds available inventory" in exc.value.detail


def test_inventory_endpoint_preserves_valid_fifo_response():
    request = InventoryValuationRequest(
        txns=[
            {"txn_type": "purchase", "quantity": 10, "unit_cost": 12},
            {"txn_type": "sale", "quantity": 2, "unit_cost": 0},
        ],
        method="FIFO",
    )

    result = inventory_valuation_endpoint(request)

    assert result["method"] == "FIFO"
    assert result["closing_quantity"] == 8
    assert result["closing_inventory_value"] == 96
    assert result["cogs"] == 24
