"""Request-boundary regression tests for boolean tax numeric inputs."""
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.tax import GstInvoiceLineIn, GstRequest, Gstr3bRequest, IncomeTaxRequest, TdsRequest


@pytest.mark.parametrize(
    ("model", "payload", "field"),
    [
        (GstRequest, {"taxable_value": 100, "gst_rate_pct": 18, "is_interstate": True}, "taxable_value"),
        (GstRequest, {"taxable_value": 100, "gst_rate_pct": 18, "is_interstate": True}, "gst_rate_pct"),
        (GstInvoiceLineIn, {"taxable_value": 100, "gst_rate_pct": 18, "is_interstate": True}, "taxable_value"),
        (GstInvoiceLineIn, {"taxable_value": 100, "gst_rate_pct": 18, "is_interstate": True}, "gst_rate_pct"),
        (Gstr3bRequest, {"lines": [], "input_tax_credit": 0}, "input_tax_credit"),
        (TdsRequest, {"amount_paid": 1000, "section": "194J"}, "amount_paid"),
        (IncomeTaxRequest, {"gross_salary": 100000, "other_income": 0}, "gross_salary"),
        (IncomeTaxRequest, {"gross_salary": 100000, "other_income": 0}, "other_income"),
    ],
)
@pytest.mark.parametrize("value", [True, False])
def test_tax_request_models_reject_boolean_numeric_values(model, payload, field, value):
    invalid = {**payload, field: value}

    with pytest.raises(ValidationError, match="numeric, not boolean"):
        model(**invalid)


def test_tax_request_models_continue_accepting_integer_amounts_and_rates():
    gst = GstRequest(taxable_value=1000, gst_rate_pct=18, is_interstate=True)
    line = GstInvoiceLineIn(taxable_value=1000, gst_rate_pct=18, is_interstate=False)
    summary = Gstr3bRequest(lines=[line], input_tax_credit=100)
    tds = TdsRequest(amount_paid=10000, section="194J")
    income = IncomeTaxRequest(gross_salary=900000, other_income=50000)

    assert gst.taxable_value == 1000.0
    assert summary.input_tax_credit == 100.0
    assert tds.amount_paid == 10000.0
    assert income.other_income == 50000.0
