import sys
from pathlib import Path

# CI workflows invoke pytest from different working directories.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Regression tests for strict journal-line numeric inputs."""
import pytest
from pydantic import ValidationError

from app.routers.accounting import LedgerLineIn


def _line(**overrides):
    values = {
        "account_name": "Cash",
        "account_type": "asset",
        "debit": 100,
        "credit": 0,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    "field,value",
    [
        ("debit", True),
        ("credit", False),
        ("gst_rate_pct", True),
        ("gst_taxable_value", False),
        ("tds_rate", True),
        ("tds_amount", False),
    ],
)
def test_boolean_values_are_not_accepted_as_financial_amounts(field, value):
    with pytest.raises(ValidationError):
        LedgerLineIn(**_line(**{field: value}))


def test_integer_amounts_remain_valid_numeric_inputs():
    line = LedgerLineIn(**_line(debit=100, credit=0, gst_rate_pct=18))
    assert line.debit == 100.0
    assert line.gst_rate_pct == 18.0


def test_balanced_journal_line_side_values_can_be_zero():
    line = LedgerLineIn(**_line(debit=100.0, credit=0.0))
    assert line.debit == 100.0
    assert line.credit == 0.0
