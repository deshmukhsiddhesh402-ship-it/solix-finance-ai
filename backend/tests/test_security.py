"""Regression tests for authentication hardening and router importability."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import MAX_OTP_ATTEMPTS, _OTP_STORE, generate_otp, verify_otp


def test_otp_is_single_use():
    email = "otp-once@example.test"
    otp = generate_otp(email)
    assert verify_otp(email, otp) is True
    assert verify_otp(email, otp) is False


def test_otp_is_case_insensitive_and_rate_limited():
    email = "otp-cooldown@example.test"
    otp = generate_otp(email)
    assert verify_otp(email.upper(), otp) is True
    with pytest.raises(ValueError):
        generate_otp(email)


def test_otp_expires_after_maximum_failed_attempts():
    email = "otp-attempts@example.test"
    otp = generate_otp(email)
    for _ in range(MAX_OTP_ATTEMPTS):
        assert verify_otp(email, "not-the-issued-code") is False
    assert verify_otp(email, otp) is False
    assert email not in _OTP_STORE


def test_production_rejects_short_jwt_secret():
    with pytest.raises(ValidationError):
        Settings(
            ENV="production",
            JWT_SECRET="too-short",
            DATABASE_URL="postgresql://user:password@db:5432/solix",
        )


def test_accounting_router_imports():
    from app.routers.accounting import router

    assert any(route.path.endswith("/journal-entries") for route in router.routes)
