"""Regression tests for API-key generation, verification, and display masking."""
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.api_key_engine import (
    API_KEY_PREFIX,
    generate_api_key,
    hash_api_key,
    mask_api_key,
    verify_api_key,
)


def test_generated_api_key_has_expected_prefix_and_stores_only_digest():
    plaintext, stored_hash = generate_api_key()

    assert plaintext.startswith(API_KEY_PREFIX)
    assert len(stored_hash) == 64  # SHA-256 hex digest
    assert stored_hash == hash_api_key(plaintext)
    assert plaintext != stored_hash


def test_generated_api_keys_are_distinct():
    first, first_hash = generate_api_key()
    second, second_hash = generate_api_key()

    assert first != second
    assert first_hash != second_hash


def test_api_key_verification_accepts_only_matching_key():
    plaintext, stored_hash = generate_api_key()

    assert verify_api_key(plaintext, stored_hash)
    assert not verify_api_key(plaintext + "tampered", stored_hash)
    assert not verify_api_key("solix_invalid", stored_hash)


def test_masked_api_key_keeps_recognizable_prefix_and_suffix_only():
    plaintext, _ = generate_api_key()

    masked = mask_api_key(plaintext)

    assert masked == f"{plaintext[:10]}...{plaintext[-4:]}"
    assert plaintext not in masked


def test_short_api_keys_are_fully_masked():
    assert mask_api_key("short") == "•••••"
    assert mask_api_key("") == ""
