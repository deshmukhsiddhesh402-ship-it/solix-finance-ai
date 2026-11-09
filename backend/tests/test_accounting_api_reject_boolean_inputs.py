"""API-boundary regression tests for boolean financial numeric inputs."""
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.accounting import InventoryTxnIn, LedgerLineIn, StraightLineRequest, WdvRequest


@pytest.mark.parametrize(
    "field",
    ["debit", "credit", "gst_rate_pct", "gst_taxable_value", "tds_rate", "tds_amount"],
)
@pytest.mark.parametrize("value", [True, False])
def test_journal_line_rejects_boolean_financial_values(field, value):
    payload = {"account_name": "Cash", "account_type": "asset", "debit": 100, "credit": 0}
    payload[field] = value

    with pytest.raises(ValidationError, match="numeric, not boolean"):
        LedgerLineIn(**payload)


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (StraightLineRequest, {"cost": 100, "salvage": 0, "useful_life_years": 5}, "cost"),
        (StraightLineRequest, {"cost": 100, "salvage": 0, "useful_life_years": 5}, "salvage"),
        (StraightLineRequest, {"cost": 100, "salvage": 0, "useful_life_years": 5}, "useful_life_years"),
        (WdvRequest, {"cost": 100, "rate_pct": 15, "years": 5}, "cost"),
        (WdvRequest, {"cost": 100, "rate_pct": 15, "years": 5}, "rate_pct"),
        (WdvRequest, {"cost": 100, "rate_pct": 15, "years": 5}, "years"),
        (InventoryTxnIn, {"txn_type": "purchase", "quantity": 2, "unit_cost": 50}, "quantity"),
        (InventoryTxnIn, {"txn_type": "purchase", "quantity": 2, "unit_cost": 50}, "unit_cost"),
    ],
)
@pytest.mark.parametrize("value", [True, False])
def test_depreciation_and_inventory_requests_reject_boolean_numbers(model, payload, field, value):
    invalid = {**payload, field: value}

    with pytest.raises(ValidationError, match="numeric, not boolean"):
        model(**invalid)


def test_accounting_request_models_continue_accepting_integer_financial_values():
    line = LedgerLineIn(account_name="Cash", account_type="asset", debit=100, credit=0)
    straight_line = StraightLineRequest(cost=100, salvage=0, useful_life_years=5)
    wdv = WdvRequest(cost=100, rate_pct=15, years=5)
    inventory = InventoryTxnIn(txn_type="purchase", quantity=2, unit_cost=50)

    assert line.debit == 100.0
    assert straight_line.cost == 100.0
    assert straight_line.useful_life_years == 5
    assert wdv.rate_pct == 15.0
    assert wdv.years == 5
    assert inventory.quantity == 2.0
