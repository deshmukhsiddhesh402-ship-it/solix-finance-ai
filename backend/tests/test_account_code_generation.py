"""Regression tests for automatically generated chart-of-account codes."""

from app.routers.accounting import _new_account_code


def test_generated_account_codes_are_valid_and_compact():
    code = _new_account_code("Office Supplies")
    assert code.startswith("OFFIC-")
    assert len(code) <= 20
    assert code.isascii()
    assert code.replace("-", "").isalnum()


def test_similar_account_names_do_not_share_a_deterministic_prefix_code():
    # These names collided under the previous account_name[:10].upper() scheme.
    first = _new_account_code("Office Supplies")
    second = _new_account_code("Office Salary")
    assert first != second
