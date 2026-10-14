"""Regression tests for untrusted invoice amounts used to create journal lines."""
import pytest

from app.services.invoice_ocr_engine import invoice_to_journal_lines


def valid_invoice(**overrides):
    invoice = {
        "vendor_name": "Example Supplies",
        "taxable_value": 100.00,
        "cgst_amount": 9.00,
        "sgst_amount": 9.00,
        "igst_amount": 0.00,
        "total_amount": 118.00,
    }
    invoice.update(overrides)
    return invoice


def test_valid_invoice_amounts_produce_balanced_journal():
    lines = invoice_to_journal_lines(valid_invoice())

    assert sum(line["debit"] for line in lines) == pytest.approx(118.00)
    assert sum(line["credit"] for line in lines) == pytest.approx(118.00)


@pytest.mark.parametrize("value", [True, False, [], {}, "not-a-number"])
def test_invalid_amount_types_are_rejected(value):
    with pytest.raises(ValueError, match="must be numeric"):
        invoice_to_journal_lines(valid_invoice(taxable_value=value))


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", float("nan"), float("inf"), float("-inf")])
def test_non_finite_amounts_are_rejected(value):
    with pytest.raises(ValueError, match="finite"):
        invoice_to_journal_lines(valid_invoice(taxable_value=value))


def test_negative_amount_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        invoice_to_journal_lines(valid_invoice(cgst_amount=-1))


def test_extreme_values_cannot_create_non_finite_journal_totals():
    with pytest.raises(ValueError, match="numeric range"):
        invoice_to_journal_lines(valid_invoice(
            taxable_value=1e308,
            cgst_amount=1e308,
            sgst_amount=0,
            igst_amount=0,
            total_amount=None,
        ))


@pytest.mark.parametrize("account", ["", "   ", None, 42])
def test_expense_account_must_be_a_non_empty_name(account):
    with pytest.raises(ValueError, match="Expense account"):
        invoice_to_journal_lines(valid_invoice(), expense_account=account)
