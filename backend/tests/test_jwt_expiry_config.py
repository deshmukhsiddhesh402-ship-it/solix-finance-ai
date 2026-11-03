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
