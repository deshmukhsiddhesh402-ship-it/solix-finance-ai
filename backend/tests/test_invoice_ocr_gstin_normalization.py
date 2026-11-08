"""Regression tests for normalized GSTIN handling in invoice OCR."""

import pytest

from app.services.invoice_ocr_engine import extract_state_code, is_valid_gstin_format


def test_extract_state_code_uses_trimmed_uppercase_gstin():
    gstin = " 27abcde1234f1z5 "

    assert is_valid_gstin_format(gstin) is True
    assert extract_state_code(gstin) == "27"


@pytest.mark.parametrize("value", [None, 0, 12345, [], {}, True])
def test_gstin_helpers_reject_non_string_values(value):
    assert is_valid_gstin_format(value) is False
    assert extract_state_code(value) is None


def test_gstin_format_trims_surrounding_whitespace_before_matching():
    gstin = "27ABCDE1234F1Z5" + chr(10)
    assert is_valid_gstin_format(gstin) is True
    assert extract_state_code(gstin) == "27"


def test_gstin_format_rejects_non_whitespace_suffix():
    assert is_valid_gstin_format("27ABCDE1234F1Z5X") is False
    assert extract_state_code("27ABCDE1234F1Z5X") is None


def test_extract_state_code_returns_none_for_invalid_format():
    assert extract_state_code("not-a-gstin") is None
