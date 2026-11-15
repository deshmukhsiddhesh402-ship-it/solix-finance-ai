"""Validation tests for human-entered inventory source references."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.routers.accounting import InventoryTransactionCreate


@pytest.mark.parametrize(
    "reference_no",
    [
        "INV\\n2026-001",
        "INV\\r2026-001",
        "INV\\t2026-001",
        "INV\\x002026-001",
        "INV\\x7f2026-001",
        "INV\\u00852026-001",
        "\\nINV-2026-001",
    ],
)
def test_inventory_reference_rejects_control_characters(reference_no):
    with pytest.raises(ValidationError, match="reference_no must not contain control characters"):
        InventoryTransactionCreate(
            txn_type="purchase",
            txn_date=date(2026, 11, 15),
            quantity=Decimal("1.0000"),
            unit_cost=Decimal("2.0000"),
            reference_no=reference_no,
        )


def test_inventory_reference_trims_spaces_and_preserves_unicode():
    payload = InventoryTransactionCreate(
        txn_type="purchase",
        txn_date=date(2026, 11, 15),
        quantity=Decimal("1.0000"),
        unit_cost=Decimal("2.0000"),
        reference_no="  发票-2026-001  ",
    )

    assert payload.reference_no == "发票-2026-001"
