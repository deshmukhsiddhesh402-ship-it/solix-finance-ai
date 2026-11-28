from app.services.api_key_engine import generate_api_key, is_valid_api_key_format, verify_api_key


def test_generated_api_key_matches_expected_format_and_verifies():
    plaintext, stored_hash = generate_api_key()
    assert is_valid_api_key_format(plaintext)
    assert verify_api_key(plaintext, stored_hash)


def test_api_key_verification_rejects_malformed_values():
    _, stored_hash = generate_api_key()
    for candidate in ["", "other_" + "a" * 43, "solix_short", "solix_" + "!" * 43]:
        assert not verify_api_key(candidate, stored_hash)


def test_api_key_verification_rejects_oversized_and_non_string_values():
    _, stored_hash = generate_api_key()
    assert not verify_api_key("solix_" + "a" * 5000, stored_hash)
    assert not verify_api_key(None, stored_hash)
    assert not verify_api_key("solix_" + "a" * 43, "not-a-sha256-digest")


def test_valid_format_with_wrong_hash_does_not_verify():
    plaintext, _ = generate_api_key()
    assert not verify_api_key(plaintext, "0" * 64)
