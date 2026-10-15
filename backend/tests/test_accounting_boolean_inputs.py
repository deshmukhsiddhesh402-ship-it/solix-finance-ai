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
