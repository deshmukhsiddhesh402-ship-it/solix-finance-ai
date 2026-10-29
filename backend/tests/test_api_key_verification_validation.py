"""Regression tests for malformed API-key verification inputs."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.api_key_engine import generate_api_key, verify_api_key


def test_generated_api_key_still_verifies():
    plaintext, stored_hash = generate_api_key()
    assert verify_api_key(plaintext, stored_hash)


def test_malformed_key_or_digest_fails_closed():
    assert not verify_api_key(None, "0" * 64)
    assert not verify_api_key("not-solix-key", "0" * 64)
    assert not verify_api_key("solix_example", None)
    assert not verify_api_key("solix_example", "not-a-digest")
    assert not verify_api_key("solix_example", "g" * 64)
    assert not verify_api_key("solix_example", "0" * 63)


def test_valid_format_but_wrong_digest_does_not_verify():
    assert not verify_api_key("solix_example", "0" * 64)
