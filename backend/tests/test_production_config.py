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
