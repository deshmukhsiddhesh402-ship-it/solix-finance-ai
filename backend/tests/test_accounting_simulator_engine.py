"""Regression tests for the additive Decimal-based simulator primitives."""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.accounting_simulator_engine import (
    JournalEntry,
    JournalLine,
    build_general_ledger,
    build_trial_balance,
    money,
    validate_journal_entry,
)


def test_balanced_compound_entry_uses_exact_paisa_precision():
    entry = JournalEntry((
        JournalLine("Rent Expense", debit="1000.00"),
        JournalLine("GST Input Credit", debit="180.00"),
        JournalLine("Cash", credit="1180.00"),
    ))
    result = validate_journal_entry(entry)
    assert result["is_balanced"] is True
    assert result["total_debit"] == Decimal("1180.00")
    assert result["total_credit"] == Decimal("1180.00")


def test_balanced_compound_entry_with_multiple_credit_lines():
    entry = JournalEntry((
        JournalLine("Computer Equipment", debit="10000.00"),
        JournalLine("Bank", credit="8000.00"),
        JournalLine("Accounts Payable", credit="2000.00"),
    ))
    result = validate_journal_entry(entry)
    assert result["total_debit"] == result["total_credit"] == Decimal("10000.00")


def test_rejects_unbalanced_entry_by_one_paisa():
    entry = JournalEntry((
        JournalLine("Expense", debit="100.00"),
        JournalLine("Cash", credit="99.99"),
    ))
    with pytest.raises(ValueError, match="unbalanced"):
        validate_journal_entry(entry)


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "1.001", True, "not-money"])
def test_money_rejects_invalid_amounts(amount):
    with pytest.raises(ValueError):
        money(amount)


def test_float_input_is_converted_through_decimal_string():
    assert money(0.1) + money(0.2) == Decimal("0.30")


def test_journal_line_cannot_have_both_sides_or_no_amount():
    with pytest.raises(ValueError, match="both debit and credit"):
        validate_journal_entry(JournalEntry((
            JournalLine("A", debit="10.00", credit="10.00"),
            JournalLine("B", debit="1.00"),
        )))
    with pytest.raises(ValueError, match="must contain a debit or credit"):
        validate_journal_entry(JournalEntry((
            JournalLine("A", debit="0.00", credit="0.00"),
            JournalLine("B", debit="1.00"),
        )))


def test_general_ledger_and_trial_balance_reconcile():
    entries = [
        JournalEntry((
            JournalLine("Cash", debit="5000.00"),
            JournalLine("Capital", credit="5000.00"),
        )),
        JournalEntry((
            JournalLine("Rent Expense", debit="500.00"),
            JournalLine("Cash", credit="500.00"),
        )),
    ]
    ledger = build_general_ledger(entries)
    assert ledger["Cash"]["balance"] == Decimal("4500.00")
    assert ledger["Cash"]["balance_side"] == "debit"
    assert ledger["Capital"]["balance_side"] == "credit"
    assert ledger["Rent Expense"]["balance_side"] == "debit"

    trial_balance = build_trial_balance(ledger)
    assert trial_balance["is_balanced"] is True
    assert trial_balance["total_debit"] == Decimal("5000.00")
    assert trial_balance["total_credit"] == Decimal("5000.00")


def test_general_ledger_refuses_unbalanced_source_entry():
    entries = [JournalEntry((
        JournalLine("Cash", debit="100.00"),
        JournalLine("Capital", credit="90.00"),
    ))]
    with pytest.raises(ValueError, match="unbalanced"):
        build_general_ledger(entries)


def test_large_amounts_remain_exact_to_paisa():
    entry = JournalEntry((
        JournalLine("Bank", debit="1000000000.01"),
        JournalLine("Capital", credit="1000000000.01"),
    ))
    result = validate_journal_entry(entry)
    assert result["total_debit"] == Decimal("1000000000.01")


@pytest.mark.parametrize(
    "debit,credit,expected_side,c_d_side,b_d_side,expected_balance",
    [
        ("150.00", "100.00", "debit", "credit", "debit", Decimal("50.00")),
        ("100.00", "150.00", "credit", "debit", "credit", Decimal("50.00")),
        ("100.00", "100.00", "zero", None, None, Decimal("0.00")),
    ],
)
def test_t_account_balancing_conventions(
    debit, credit, expected_side, c_d_side, b_d_side, expected_balance
):
    from app.services.accounting_simulator_engine import build_t_account

    result = build_t_account(debit, credit)
    assert result["balance_side"] == expected_side
    assert result["balance_c_d_side"] == c_d_side
    assert result["balance_b_d_side"] == b_d_side
    assert result["balance"] == expected_balance


def test_educational_narration_validator_checks_prefix_words_and_keywords():
    from app.services.accounting_simulator_engine import validate_educational_narration

    good = validate_educational_narration(
        "Being monthly rent paid in cash",
        required_keywords=("rent", "cash"),
    )
    assert good["is_valid"] is True
    assert good["errors"] == []

    bad = validate_educational_narration(
        "Paid rent today", required_keywords=("rent", "cash")
    )
    assert bad["is_valid"] is False
    assert any("Being" in error for error in bad["errors"])
    assert any("five words" in error for error in bad["errors"])
    assert any("cash" in error for error in bad["errors"])


def test_narration_style_does_not_block_general_journal_validation():
    entry = JournalEntry((
        JournalLine("Rent Expense", debit="100.00"),
        JournalLine("Cash", credit="100.00"),
    ), narration="Rent paid")
    assert validate_journal_entry(entry)["is_balanced"] is True


def test_cash_book_calculates_closing_balance_exactly():
    from app.services.accounting_simulator_engine import build_cash_book

    result = build_cash_book(
        "1000.00",
        receipts=[
            {"description": "Cash sales", "amount": "250.50"},
            {"description": "Owner contribution", "amount": "100.00"},
        ],
        payments=[{"description": "Office supplies", "amount": "75.25"}],
    )
    assert result["total_receipts"] == Decimal("350.50")
    assert result["total_payments"] == Decimal("75.25")
    assert result["closing_balance"] == Decimal("1275.25")


def test_cash_book_rejects_payment_overdraft():
    from app.services.accounting_simulator_engine import build_cash_book

    with pytest.raises(ValueError, match="cash cannot be negative"):
        build_cash_book(
            "100.00",
            receipts=[],
            payments=[{"description": "Payment", "amount": "100.01"}],
        )


@pytest.mark.parametrize(
    "receipts,payments",
    [
        ([{"description": "", "amount": "10.00"}], []),
        ([{"description": "Sales", "amount": "0.00"}], []),
        ([{"description": "Sales", "amount": "1.001"}], []),
        ([], [{"description": "Supplies", "amount": "-1.00"}]),
        ([{"description": "Sales", "amount": "10.00"}], ["invalid"]),
    ],
)
def test_cash_book_rejects_invalid_transactions(receipts, payments):
    from app.services.accounting_simulator_engine import build_cash_book

    with pytest.raises(ValueError):
        build_cash_book("0.00", receipts=receipts, payments=payments)


def test_accounting_cycle_connects_journal_ledger_and_trial_balance():
    from app.services.accounting_simulator_engine import build_accounting_cycle

    entries = [
        JournalEntry((
            JournalLine("Cash", debit="5000.00"),
            JournalLine("Owner Capital", credit="5000.00"),
        )),
        JournalEntry((
            JournalLine("Office Rent", debit="750.00"),
            JournalLine("Cash", credit="750.00"),
        )),
        JournalEntry((
            JournalLine("Stationery Expense", debit="125.50"),
            JournalLine("Cash", credit="125.50"),
        )),
    ]
    result = build_accounting_cycle(entries)
    assert result["journal_entry_count"] == 3
    assert result["is_balanced"] is True
    assert result["ledger"]["Cash"]["balance"] == Decimal("4124.50")
    assert result["ledger"]["Cash"]["balance_side"] == "debit"
    assert result["trial_balance"]["total_debit"] == Decimal("5000.00")
    assert result["trial_balance"]["total_credit"] == Decimal("5000.00")


def test_accounting_cycle_rejects_unbalanced_journal_entry():
    from app.services.accounting_simulator_engine import build_accounting_cycle

    with pytest.raises(ValueError, match="unbalanced"):
        build_accounting_cycle([
            JournalEntry((
                JournalLine("Cash", debit="100.00"),
                JournalLine("Capital", credit="99.00"),
            ))
        ])


def test_accounting_cycle_accepts_empty_practice_set_as_balanced():
    from app.services.accounting_simulator_engine import build_accounting_cycle

    result = build_accounting_cycle([])
    assert result["journal_entry_count"] == 0
    assert result["ledger"] == {}
    assert result["trial_balance"]["is_balanced"] is True
    assert result["trial_balance"]["total_debit"] == Decimal("0.00")

