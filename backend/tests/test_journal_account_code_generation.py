"""Regression tests for collision-resistant auto-generated account codes."""
import re

from app.routers.accounting import _new_account_code


def test_auto_account_codes_fit_schema_and_have_safe_readable_prefixes():
    code = _new_account_code("Office Supplies")

    assert len(code) <= 20
    assert re.fullmatch(r"[A-Z0-9]{1,5}-[A-F0-9]{14}", code)
    assert code.startswith("OFFIC-")


def test_distinct_account_names_with_same_prefix_get_distinct_codes():
    first = _new_account_code("Office Supplies")
    second = _new_account_code("Office Salary")

    assert first != second
    assert first.split("-", 1)[0] == second.split("-", 1)[0]


def test_blank_or_punctuation_only_names_use_safe_fallback_prefix():
    code = _new_account_code(" !!! ")

    assert code.startswith("ACCT-")
    assert len(code) <= 20
