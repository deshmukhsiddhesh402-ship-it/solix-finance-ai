"""Regression tests for OCR invoice-to-journal conversion validation."""
import sys
import os
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.invoice_ocr_engine import invoice_to_journal_lines


def valid_invoice(**overrides):
    invoice = {
        "vendor_name": "Acme Supplies",
        "taxable_value": 1000,
        "cgst_amount": 90,
        "sgst_amount": 90,
        "igst_amount": 0,
        "total_amount": 1180,
    }
    invoice.update(overrides)
    return invoice


def test_invoice_to_journal_lines_returns_balanced_legacy_shape():
    lines = invoice_to_journal_lines(valid_invoice())
    assert lines[0] == {
        "account_name": "Purchases",
        "account_type": "expense",
        "debit": 1000.0,
        "credit": 0.0,
    }
    assert lines[-1]["account_name"] == "Acme Supplies (Payable)"
    assert round(sum(line["debit"] for line in lines), 2) == round(
        sum(line["credit"] for line in lines), 2
    )


def test_invoice_zero_tax_values_are_valid_and_missing_total_is_derived():
    invoice = {"taxable_value": Decimal("10.005"), "cgst_amount": 0, "sgst_amount": 0, "igst_amount": 0}
    lines = invoice_to_journal_lines(invoice)
    assert lines[0]["debit"] == 10.01
    assert lines[-1]["credit"] == 10.01
    assert lines[-1]["account_name"] == "Unknown Vendor (Payable)"


@pytest.mark.parametrize("bad", [True, False, "100", None, float("nan"), float("inf"), float("-inf"), 10**1000])
@pytest.mark.parametrize("field", ["taxable_value", "cgst_amount", "sgst_amount", "igst_amount", "total_amount"])
def test_invoice_amounts_reject_invalid_explicit_values(field, bad):
    invoice = valid_invoice()
    invoice[field] = bad
    with pytest.raises(ValueError):
        invoice_to_journal_lines(invoice)


@pytest.mark.parametrize("bad", [-0.01, Decimal("-1")])
def test_invoice_amounts_reject_negative_values(bad):
    with pytest.raises(ValueError, match="negative"):
        invoice_to_journal_lines(valid_invoice(cgst_amount=bad))


def test_invoice_amounts_use_decimal_half_up_rounding():
    lines = invoice_to_journal_lines({
        "taxable_value": Decimal("2.675"),
        "cgst_amount": 0,
        "sgst_amount": 0,
        "igst_amount": 0,
        "total_amount": Decimal("2.68"),
    })
    assert lines[0]["debit"] == 2.68
    assert lines[-1]["credit"] == 2.68


@pytest.mark.parametrize("total", [1179.98, 1179.99, 1179.00, 1200])
def test_invoice_rejects_post_rounding_total_mismatch(total):
    with pytest.raises(ValueError, match="does not reconcile"):
        invoice_to_journal_lines(valid_invoice(total_amount=total))


@pytest.mark.parametrize("vendor", [123, [], "", "   ", "Acme\nSupplies"])
def test_invoice_rejects_malformed_vendor_names(vendor):
    with pytest.raises(ValueError):
        invoice_to_journal_lines(valid_invoice(vendor_name=vendor))


@pytest.mark.parametrize("account", [None, 42, "", "   ", "Purchases\nOther"])
def test_invoice_rejects_malformed_expense_account(account):
    with pytest.raises(ValueError):
        invoice_to_journal_lines(valid_invoice(), expense_account=account)


def test_invoice_rejects_non_dictionary_input():
    with pytest.raises(ValueError, match="dictionary"):
        invoice_to_journal_lines([])


def test_missing_optional_tax_fields_default_to_zero_but_explicit_none_does_not():
    lines = invoice_to_journal_lines({"taxable_value": 100, "total_amount": 100})
    assert lines[-1]["credit"] == 100
    with pytest.raises(ValueError):
        invoice_to_journal_lines({"taxable_value": 100, "cgst_amount": None, "total_amount": 100})


def test_max_supported_currency_value_is_accepted_and_overflow_rejected():
    max_amount = Decimal("9999999999999.99")
    lines = invoice_to_journal_lines({"taxable_value": max_amount, "total_amount": max_amount})
    assert Decimal(str(lines[0]["debit"])).quantize(Decimal("0.01")) == max_amount
    with pytest.raises(ValueError, match="limit"):
        invoice_to_journal_lines({"taxable_value": Decimal("10000000000000.00"), "total_amount": Decimal("1000000000000000")})


def test_taxable_value_is_required_instead_of_silently_defaulting_to_zero():
    with pytest.raises(ValueError, match="required"):
        invoice_to_journal_lines({"total_amount": 0})
