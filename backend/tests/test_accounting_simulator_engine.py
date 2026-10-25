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
