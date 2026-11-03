"""Production configuration security regression tests."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _production_settings(**overrides):
    values = {
        "ENV": "production",
        "JWT_SECRET": "x" * 40,
        "DATABASE_URL": "postgresql://db.example.com/solix",
        "ALLOWED_ORIGINS": ["https://app.example.com"],
    }
    values.update(overrides)
    return Settings(**values)


def test_production_accepts_a_valid_https_origin():
    settings = _production_settings()
    assert settings.ALLOWED_ORIGINS == ["https://app.example.com"]


@pytest.mark.parametrize(
    "origin",
    [
        "http://app.example.com",
        "https://user@app.example.com",
        "https://app.example.com/path",
        "https://app.example.com?token=value",
        "https://app.example.com#fragment",
        "https://app.example.com:99999",
        "https://localhost",
        "*",
    ],
)
def test_production_rejects_non_origin_or_insecure_cors_values(origin):
    with pytest.raises(ValidationError):
        _production_settings(ALLOWED_ORIGINS=[origin])

@pytest.mark.parametrize("secret", [" " * 40, " short ".ljust(40)])
def test_production_rejects_jwt_secrets_with_insufficient_non_whitespace_length(secret):
    with pytest.raises(ValidationError):
        _production_settings(JWT_SECRET=secret)

@pytest.mark.parametrize("expiry", [0, -1, 10081])
def test_settings_reject_jwt_expiry_outside_supported_range(expiry):
    with pytest.raises(ValidationError):
        _production_settings(JWT_EXPIRE_MINUTES=expiry)


def test_settings_accept_maximum_supported_jwt_expiry():
    settings = _production_settings(JWT_EXPIRE_MINUTES=10080)
    assert settings.JWT_EXPIRE_MINUTES == 10080
