"""Regression tests for boolean coercion in accounting journal inputs."""
import pytest
from pydantic import ValidationError

from app.routers.accounting import LedgerLineIn


@pytest.mark.parametrize(
    "field_name",
    ["debit", "credit", "gst_rate_pct", "gst_taxable_value", "tds_rate", "tds_amount"],
)
def test_ledger_line_rejects_boolean_numeric_values(field_name):
    payload = {
        "account_name": "Office expense",
        "account_type": "expense",
        "debit": 100.0,
        "credit": 0.0,
    }
    payload[field_name] = True

    with pytest.raises(ValidationError, match="not boolean"):
        LedgerLineIn(**payload)


def test_ledger_line_accepts_regular_numeric_values():
    line = LedgerLineIn(
        account_name="Office expense",
        account_type="expense",
        debit=100.0,
        credit=0.0,
        gst_rate_pct=18.0,
        gst_taxable_value=100.0,
        tds_rate=10.0,
        tds_amount=10.0,
    )

    assert line.debit == 100.0
    assert line.gst_rate_pct == 18.0
    assert line.tds_amount == 10.0

@pytest.mark.parametrize(
    "model_type,payload,field_name",
    [
        ("ratios", {
            "current_assets": 10, "current_liabilities": 5, "inventory": 1,
            "total_debt": 2, "total_equity": 4, "net_profit": 1,
            "revenue": 20, "total_assets": 30,
        }, "current_assets"),
        ("straight_line", {"cost": 100, "salvage": 10, "useful_life_years": 5}, "cost"),
        ("wdv", {"cost": 100, "rate_pct": 10, "years": 5}, "rate_pct"),
        ("inventory", {"txn_type": "purchase", "quantity": 2, "unit_cost": 10}, "quantity"),
    ],
)
def test_finance_calculator_models_reject_boolean_numeric_values(model_type, payload, field_name):
    from app.routers.accounting import (
        InventoryTxnIn, RatiosRequest, StraightLineRequest, WdvRequest,
    )

    models = {
        "ratios": RatiosRequest,
        "straight_line": StraightLineRequest,
        "wdv": WdvRequest,
        "inventory": InventoryTxnIn,
    }
    payload[field_name] = True
    with pytest.raises(ValidationError, match="not boolean"):
        models[model_type](**payload)

@pytest.mark.parametrize("field_name", ["debit", "credit"])
def test_trial_balance_engine_rejects_boolean_amounts(field_name):
    from app.services.accounting_engine import LedgerLine, build_trial_balance

    values = {"account_name": "Cash", "account_type": "asset", "debit": 0.0, "credit": 0.0}
    values[field_name] = True
    with pytest.raises(ValueError, match="not boolean"):
        build_trial_balance([LedgerLine(**values)])
