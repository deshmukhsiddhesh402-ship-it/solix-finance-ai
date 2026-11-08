import pytest

from app.services.invoice_ocr_engine import invoice_to_journal_lines


def test_invoice_to_journal_lines_preserves_balanced_purchase_entry():
    lines = invoice_to_journal_lines(
        {
            "vendor_name": "Sample Vendor",
            "taxable_value": "1000.00",
            "cgst_amount": 90,
            "sgst_amount": 90,
            "total_amount": 1180,
        }
    )

    assert lines[0]["debit"] == 1000.0
    assert lines[-1]["credit"] == 1180.0
    assert round(sum(line["debit"] for line in lines), 2) == 1180.0


@pytest.mark.parametrize(
    "bad_value",
    [
        {"unexpected": "object"},
        ["100"],
        True,
        float("nan"),
        float("inf"),
        -1,
        "not-a-number",
    ],
)
def test_invoice_to_journal_lines_rejects_malformed_taxable_amounts(bad_value):
    with pytest.raises(ValueError, match="taxable_value"):
        invoice_to_journal_lines({"taxable_value": bad_value, "total_amount": 0})


def test_invoice_to_journal_lines_rejects_malformed_total_amount():
    with pytest.raises(ValueError, match="total_amount"):
        invoice_to_journal_lines({"taxable_value": 100, "total_amount": {"amount": 100}})


def test_invoice_to_journal_lines_rejects_non_object_invoice():
    with pytest.raises(ValueError, match="Invoice data must be an object"):
        invoice_to_journal_lines(["not", "an", "invoice"])  # type: ignore[arg-type]


def test_invoice_to_journal_lines_rejects_blank_expense_account():
    with pytest.raises(ValueError, match="Expense account"):
        invoice_to_journal_lines({"taxable_value": 100, "total_amount": 100}, "   ")


def test_invoice_to_journal_lines_rejects_component_sum_overflow():
    with pytest.raises(ValueError, match="supported numeric range"):
        invoice_to_journal_lines(
            {
                "taxable_value": 1e308,
                "cgst_amount": 1e308,
                "total_amount": 1e308,
            }
        )


def test_invoice_to_journal_lines_rejects_unbalanced_extracted_total():
    with pytest.raises(ValueError, match="does not reconcile"):
        invoice_to_journal_lines({"taxable_value": 100, "total_amount": 99})



def test_invoice_to_journal_lines_accepts_vendor_name_at_account_limit():
    lines = invoice_to_journal_lines(
        {"vendor_name": "V" * 245, "taxable_value": 100, "total_amount": 100}
    )

    assert len(lines[-1]["account_name"]) == 255
    assert lines[-1]["account_name"].endswith(" (Payable)")


def test_invoice_to_journal_lines_rejects_vendor_name_that_exceeds_account_limit():
    with pytest.raises(ValueError, match="maximum 245 characters"):
        invoice_to_journal_lines(
            {"vendor_name": "V" * 246, "taxable_value": 100, "total_amount": 100}
        )


def test_invoice_to_journal_lines_rejects_overlong_expense_account():
    with pytest.raises(ValueError, match="Expense account name"):
        invoice_to_journal_lines(
            {"taxable_value": 100, "total_amount": 100},
            "E" * 256,
        )
