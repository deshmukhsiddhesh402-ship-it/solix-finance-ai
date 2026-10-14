"""Tests for defensive GSTIN structural validation."""
import pytest

from app.services.invoice_ocr_engine import extract_state_code, is_valid_gstin_format


@pytest.mark.parametrize("value", [None, "", "   ", 123, True, [], {}, ["27AAPFU0939F1ZV"]])
def test_gstin_validator_returns_false_for_missing_or_malformed_types(value):
    assert is_valid_gstin_format(value) is False
    assert extract_state_code(value) is None


def test_gstin_validator_normalizes_case_and_surrounding_whitespace():
    gstin = "  27AAPFU0939F1ZV  "
    assert is_valid_gstin_format(gstin) is True
    assert extract_state_code(gstin) == "27"


@pytest.mark.parametrize("value", ["27AAPFU0939F1Z", "27AAPFU0939F1ZVextra", "XXAAPFU0939F1ZV"])
def test_gstin_validator_rejects_wrong_length_or_structure(value):
    assert is_valid_gstin_format(value) is False
