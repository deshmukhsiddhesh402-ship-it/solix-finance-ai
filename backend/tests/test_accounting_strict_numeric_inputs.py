"""Regression tests for strict numeric inputs across accounting request models."""
import pytest
from pydantic import ValidationError

from app.routers.accounting import (
    InventoryTxnIn,
    RatiosRequest,
    StraightLineRequest,
    WdvRequest,
)


@pytest.mark.parametrize(
    "field",
    [
        "current_assets", "current_liabilities", "inventory", "total_debt",
        "total_equity", "net_profit", "revenue", "total_assets",
    ],
)
def test_ratio_model_rejects_boolean_financial_values(field):
    values = {
        "current_assets": 10,
        "current_liabilities": 5,
        "inventory": 2,
        "total_debt": 3,
        "total_equity": 7,
        "net_profit": 1,
        "revenue": 20,
        "total_assets": 15,
    }
    values[field] = True
    with pytest.raises(ValidationError):
        RatiosRequest(**values)


@pytest.mark.parametrize(
    "model,values,field",
    [
        (StraightLineRequest, {"cost": 100, "salvage": 10, "useful_life_years": 5}, "cost"),
        (StraightLineRequest, {"cost": 100, "salvage": 10, "useful_life_years": 5}, "salvage"),
        (WdvRequest, {"cost": 100, "rate_pct": 20, "years": 5}, "cost"),
        (WdvRequest, {"cost": 100, "rate_pct": 20, "years": 5}, "rate_pct"),
        (InventoryTxnIn, {"txn_type": "purchase", "quantity": 2, "unit_cost": 10}, "quantity"),
        (InventoryTxnIn, {"txn_type": "purchase", "quantity": 2, "unit_cost": 10}, "unit_cost"),
    ],
)
def test_other_accounting_models_reject_boolean_financial_values(model, values, field):
    invalid = dict(values)
    invalid[field] = True
    with pytest.raises(ValidationError):
        model(**invalid)


def test_integer_and_decimal_inputs_remain_supported():
    ratios = RatiosRequest(
        current_assets=10, current_liabilities=5, inventory=2, total_debt=3,
        total_equity=7, net_profit=-1.5, revenue=20, total_assets=15,
    )
    assert ratios.current_assets == 10.0
    assert ratios.net_profit == -1.5
