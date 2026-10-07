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

from app.core.security import create_access_token, decode_access_token


def test_jwt_subject_round_trips_as_user_id():
    user_id = "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"
    token = create_access_token(user_id)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user_id


def test_otp_verify_rejects_existing_user_without_tenant_membership(monkeypatch):
    """A legacy user with org_id but no matching membership must not receive a JWT."""
    from uuid import uuid4
    from fastapi import HTTPException
    from app.models.auth_user import User
    import app.routers.auth as auth_router

    user = User(
        id=uuid4(),
        org_id=uuid4(),
        email="legacy-user@example.test",
        full_name="Legacy User",
        auth_provider="otp",
        role="accountant",
    )

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            if self.model is User:
                return user
            return None

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

    monkeypatch.setattr(auth_router, "verify_otp", lambda email, otp: True)

    def fail_if_token_created(*args, **kwargs):
        raise AssertionError("Access token must not be created for an unconfigured tenant membership.")

    monkeypatch.setattr(auth_router, "create_access_token", fail_if_token_created)

    with pytest.raises(HTTPException) as exc_info:
        auth_router.verify_otp_endpoint(
            auth_router.OtpVerifyBody(email=user.email, otp="123456"),
            FakeDB(),
        )

    assert exc_info.value.status_code == 403


def test_get_db_rolls_back_and_closes_on_request_exception(monkeypatch):
    import app.core.db as db_module

    class FakeSession:
        def __init__(self):
            self.rollback_called = False
            self.close_called = False

        def rollback(self):
            self.rollback_called = True

        def close(self):
            self.close_called = True

    session = FakeSession()
    monkeypatch.setattr(db_module, "SessionLocal", lambda: session)

    dependency = db_module.get_db()
    assert next(dependency) is session

    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert session.rollback_called is True
    assert session.close_called is True
