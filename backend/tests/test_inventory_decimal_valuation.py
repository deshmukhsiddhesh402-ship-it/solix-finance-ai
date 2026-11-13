"""Regression tests for Decimal-safe FIFO/LIFO/weighted-average valuation."""
from decimal import Decimal

import pytest

from app.services.accounting_engine import (
    InventoryTxn,
    inventory_valuation,
    inventory_valuation_decimal,
)


def test_decimal_valuation_preserves_sub_cent_costs_until_final_rounding():
    transactions = [
        InventoryTxn("purchase", Decimal("0.0003"), Decimal("0.1001")),
        InventoryTxn("sale", Decimal("0.0001")),
    ]

    exact = inventory_valuation_decimal(transactions, "FIFO")
    assert exact["closing_quantity"] == Decimal("0.0002")
    assert exact["closing_inventory_value"] == Decimal("0.00002002")
    assert exact["cogs"] == Decimal("0.00001001")

    # Existing API contract remains a rounded float response.
    public = inventory_valuation(transactions, "FIFO")
    assert public["closing_quantity"] == 0.0002
    assert public["closing_inventory_value"] == 0.0
    assert public["cogs"] == 0.0


def test_decimal_valuation_keeps_fifo_and_lifo_layer_costs_distinct():
    transactions = [
        InventoryTxn("purchase", Decimal("2"), Decimal("10.25")),
        InventoryTxn("purchase", Decimal("3"), Decimal("12.75")),
        InventoryTxn("sale", Decimal("2")),
    ]

    fifo = inventory_valuation_decimal(transactions, "FIFO")
    lifo = inventory_valuation_decimal(transactions, "LIFO")

    assert fifo["cogs"] == Decimal("20.50")
    assert fifo["closing_inventory_value"] == Decimal("38.25")
    assert lifo["cogs"] == Decimal("25.50")
    assert lifo["closing_inventory_value"] == Decimal("33.25")


def test_decimal_weighted_average_uses_decimal_layer_values():
    transactions = [
        InventoryTxn("purchase", Decimal("1"), Decimal("0.10")),
        InventoryTxn("purchase", Decimal("2"), Decimal("0.20")),
        InventoryTxn("sale", Decimal("1")),
    ]

    result = inventory_valuation_decimal(transactions, "WAVG")
    assert result["cogs"].quantize(Decimal("0.00000000000000000001")) == Decimal("0.16666666666666666667")
    assert result["closing_quantity"] == Decimal("2")
    assert result["closing_inventory_value"].quantize(Decimal("0.00000000000000000001")) == Decimal("0.33333333333333333333")


@pytest.mark.parametrize("quantity", [True, False, "1", float("nan"), float("inf"), -1, 0])
def test_decimal_valuation_rejects_invalid_quantity_values(quantity):
    with pytest.raises(ValueError):
        inventory_valuation_decimal([InventoryTxn("purchase", quantity, 10)], "FIFO")


@pytest.mark.parametrize("unit_cost", [True, "10", float("nan"), float("inf"), -1])
def test_decimal_valuation_rejects_invalid_unit_cost_values(unit_cost):
    with pytest.raises(ValueError):
        inventory_valuation_decimal([InventoryTxn("purchase", 1, unit_cost)], "FIFO")


def test_decimal_valuation_rejects_values_outside_persisted_numeric_range():
    with pytest.raises(ValueError, match=r"NUMERIC\(18,4\)"):
        inventory_valuation_decimal(
            [InventoryTxn("purchase", Decimal("100000000000000"), Decimal("1"))],
            "FIFO",
        )



def test_float_compatibility_rounding_handles_maximum_persisted_numeric_values():
    maximum = Decimal("99999999999999.9999")
    result = inventory_valuation([InventoryTxn("purchase", maximum, maximum)], "FIFO")

    assert result["closing_quantity"] == float(maximum)
    assert result["closing_inventory_value"] > 0
    assert result["cogs"] == 0.0


def test_decimal_valuation_still_rejects_sales_beyond_available_stock():
    with pytest.raises(ValueError, match="exceeds available inventory"):
        inventory_valuation_decimal([InventoryTxn("sale", Decimal("0.0001"))], "FIFO")
