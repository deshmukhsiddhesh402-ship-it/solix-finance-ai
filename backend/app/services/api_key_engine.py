"""
Module: Enterprise Features — API key management (for external
integrations). Follows the standard pattern used by Stripe/GitHub/etc:
the plaintext key is shown to the user exactly once at creation time; only
its SHA-256 hash is stored, so a database breach doesn't leak usable keys.
"""
import secrets
import hashlib
import re

API_KEY_PREFIX = "solix_"


def generate_api_key() -> tuple[str, str]:
    """Returns (plaintext_key, hashed_key). Store only the hash; show the
    plaintext to the user once and never persist it."""
    random_part = secrets.token_urlsafe(32)
    plaintext = f"{API_KEY_PREFIX}{random_part}"
    hashed = hash_api_key(plaintext)
    return plaintext, hashed


def hash_api_key(plaintext_key: str) -> str:
    return hashlib.sha256(plaintext_key.encode("utf-8")).hexdigest()


def verify_api_key(plaintext_key: str, stored_hash: str) -> bool:
    """Fail closed for malformed keys/hashes and compare valid digests in constant time."""
    if not isinstance(plaintext_key, str) or not plaintext_key.startswith(API_KEY_PREFIX):
        return False
    if not isinstance(stored_hash, str) or re.fullmatch(r"[0-9a-f]{64}", stored_hash) is None:
        return False
    return secrets.compare_digest(hash_api_key(plaintext_key), stored_hash)


def mask_api_key(plaintext_key: str) -> str:
    """For display in a UI after creation — show a recognizable prefix/suffix
    without exposing the full key, e.g. 'solix_AbCd...wXyZ'."""
    if len(plaintext_key) <= 12:
        return "•" * len(plaintext_key)
    return f"{plaintext_key[:10]}...{plaintext_key[-4:]}"
