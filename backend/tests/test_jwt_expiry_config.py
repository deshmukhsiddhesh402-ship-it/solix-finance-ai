"""Regression tests for JWT expiry configuration bounds."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _settings(expiry):
    return Settings(
        ENV="production",
        JWT_SECRET="x" * 40,
        DATABASE_URL="postgresql://db.example.com/solix",
        ALLOWED_ORIGINS=["https://app.example.com"],
        JWT_EXPIRE_MINUTES=expiry,
    )


@pytest.mark.parametrize("expiry", [0, -1, 10081])
def test_settings_reject_jwt_expiry_outside_supported_range(expiry):
    with pytest.raises(ValidationError):
        _settings(expiry)


def test_settings_accept_maximum_supported_jwt_expiry():
    settings = _settings(10080)
    assert settings.JWT_EXPIRE_MINUTES == 10080


@pytest.mark.parametrize("expiry", [0, -1, 10081, True, 1.5])
def test_token_creation_rejects_expiry_outside_integer_supported_range(monkeypatch, expiry):
    from app.core import security

    monkeypatch.setattr(security.settings, "JWT_SECRET", "s" * 40)
    with pytest.raises(ValueError, match="integer between 1 minute and 7 days"):
        security.create_access_token("user-1", expires_minutes=expiry)


def test_token_creation_accepts_one_minute_expiry(monkeypatch):
    from app.core import security

    monkeypatch.setattr(security.settings, "JWT_SECRET", "s" * 40)
    token = security.create_access_token("user-1", expires_minutes=1)
    assert security.decode_access_token(token)["sub"] == "user-1"
