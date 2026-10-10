"""Regression tests for authentication hardening and router importability."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import MAX_OTP_ATTEMPTS, _OTP_STORE, generate_otp, verify_otp


def test_otp_is_single_use():
    email = "otp-once@example.com"
    otp = generate_otp(email)
    assert verify_otp(email, otp) is True
    assert verify_otp(email, otp) is False


def test_otp_is_case_insensitive_and_rate_limited():
    email = "otp-cooldown@example.com"
    otp = generate_otp(email)
    assert verify_otp(email.upper(), otp) is True
    with pytest.raises(ValueError):
        generate_otp(email)


def test_otp_expires_after_maximum_failed_attempts():
    email = "otp-attempts@example.com"
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
        email="legacy-user@example.com",
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


def test_razorpay_payment_binding_rejects_tenant_or_plan_mismatch():
    from app.services.billing_engine import validate_gateway_payment

    order = {
        "id": "order_123",
        "amount": 299900,
        "currency": "INR",
        "notes": {"org_id": "org_a", "plan": "pro"},
    }
    payment = {
        "id": "pay_123",
        "order_id": "order_123",
        "amount": 299900,
        "currency": "INR",
        "status": "captured",
    }

    with pytest.raises(ValueError, match="organization mismatch"):
        validate_gateway_payment(order, payment, "order_123", "pay_123", "org_b", "pro")

    with pytest.raises(ValueError, match="plan mismatch"):
        validate_gateway_payment(order, payment, "order_123", "pay_123", "org_a", "enterprise")


def test_razorpay_payment_binding_rejects_uncaptured_payment():
    from app.services.billing_engine import validate_gateway_payment

    order = {
        "id": "order_123",
        "amount": 299900,
        "currency": "INR",
        "notes": {"org_id": "org_a", "plan": "pro"},
    }
    payment = {
        "id": "pay_123",
        "order_id": "order_123",
        "amount": 299900,
        "currency": "INR",
        "status": "authorized",
    }

    with pytest.raises(ValueError, match="not captured"):
        validate_gateway_payment(order, payment, "order_123", "pay_123", "org_a", "pro")


def test_copilot_service_rejects_malformed_financial_entries():
    from app.services.copilot_engine import filter_transactions

    base = {
        "account_name": "Office Expense",
        "account_type": "expense",
        "debit": 100.0,
        "credit": 0.0,
        "date": "2026-10-01",
    }

    invalid_date = {**base, "date": "2026-99-99"}
    with pytest.raises(ValueError, match="dates must use YYYY-MM-DD"):
        filter_transactions([invalid_date])

    invalid_number = {**base, "debit": float("nan")}
    with pytest.raises(ValueError, match="finite"):
        filter_transactions([invalid_number])

    invalid_account = {**base, "account_type": "cash"}
    with pytest.raises(ValueError, match="valid account_type"):
        filter_transactions([invalid_account])


def test_copilot_service_rejects_invalid_period_and_date_range():
    from datetime import date
    from app.services.copilot_engine import compare_periods, filter_transactions

    entry = {
        "account_name": "Office Expense",
        "account_type": "expense",
        "debit": 100.0,
        "credit": 0.0,
        "date": date(2026, 10, 1),
    }

    with pytest.raises(ValueError, match="valid calendar year"):
        compare_periods([entry], "0000-01", "2026-10")

    with pytest.raises(ValueError, match="start_date cannot be after end_date"):
        filter_transactions([entry], start_date=date(2026, 11, 1), end_date=date(2026, 10, 1))


def test_invoice_ocr_rejects_non_object_provider_response(monkeypatch):
    import app.routers.invoice_ocr as invoice_ocr

    monkeypatch.setattr(invoice_ocr, "ask_claude_with_image", lambda *args, **kwargs: "[]")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        invoice_ocr._extract_single_image(b"image", "image/png")

    assert exc_info.value.status_code == 502


def test_embedding_provider_rejects_non_finite_vector(monkeypatch):
    import app.services.embedding_service as embedding_service

    class FakeResult:
        embeddings = [[float("nan")] * embedding_service.EMBEDDING_DIMENSIONS]

    class FakeClient:
        def embed(self, *args, **kwargs):
            return FakeResult()

    monkeypatch.setattr(embedding_service, "_client", FakeClient())

    with pytest.raises(RuntimeError, match="non-finite"):
        embedding_service.get_embeddings(["valid text"])


def test_billing_webhook_rejects_validly_signed_malformed_json(monkeypatch):
    import hmac
    import hashlib
    import asyncio
    import app.routers.billing as billing_router

    secret = "webhook-test-secret"
    body = b"{"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    class FakeHeaders:
        def get(self, name, default=""):
            return signature if name == "X-Razorpay-Signature" else default

    class FakeRequest:
        headers = FakeHeaders()

        async def body(self):
            return body

        async def json(self):
            raise ValueError("malformed JSON")

    monkeypatch.setattr(billing_router.settings, "RAZORPAY_WEBHOOK_SECRET", secret)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(billing_router.razorpay_webhook(FakeRequest(), None))

    assert exc_info.value.status_code == 400


def test_billing_webhook_rejects_signed_non_object_json(monkeypatch):
    import hmac
    import hashlib
    import asyncio
    import app.routers.billing as billing_router

    secret = "webhook-test-secret"
    body = b"[]"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    class FakeHeaders:
        def get(self, name, default=""):
            return signature if name == "X-Razorpay-Signature" else default

    class FakeRequest:
        headers = FakeHeaders()

        async def body(self):
            return body

        async def json(self):
            return []

    monkeypatch.setattr(billing_router.settings, "RAZORPAY_WEBHOOK_SECRET", secret)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(billing_router.razorpay_webhook(FakeRequest(), None))

    assert exc_info.value.status_code == 400


def test_rag_service_rejects_oversized_chunks_and_invalid_embeddings():
    from app.services.rag_engine import build_index, semantic_retrieve

    with pytest.raises(ValueError, match="chunk exceeds"):
        build_index(["x" * 20_001])

    with pytest.raises(ValueError, match="invalid values"):
        semantic_retrieve(None, "document-id", [float("nan")] * 1024)

    with pytest.raises(ValueError, match="unexpected dimension"):
        semantic_retrieve(None, "document-id", [0.0] * 10)


def test_auth_and_enterprise_share_one_org_membership_mapping():
    from app.models.auth_user import OrgMembership as AuthOrgMembership
    from app.models.enterprise import OrgMembership as EnterpriseOrgMembership

    assert AuthOrgMembership is EnterpriseOrgMembership


def test_billing_failed_webhook_does_not_downgrade_a_different_recorded_order(monkeypatch):
    import hmac
    import hashlib
    import asyncio
    import json
    import app.routers.billing as billing_router

    secret = "webhook-test-secret"
    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "order_id": "order-old",
                    "notes": {"org_id": "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"},
                }
            }
        },
    }
    body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    class FakeHeaders:
        def get(self, name, default=""):
            return signature if name == "X-Razorpay-Signature" else default

    class FakeRequest:
        headers = FakeHeaders()

        async def body(self):
            return body

        async def json(self):
            return payload

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class FakeDB:
        def __init__(self):
            self.commit_called = False

        def query(self, model):
            return FakeQuery()

        def commit(self):
            self.commit_called = True

    db = FakeDB()
    monkeypatch.setattr(billing_router.settings, "RAZORPAY_WEBHOOK_SECRET", secret)

    result = asyncio.run(billing_router.razorpay_webhook(FakeRequest(), db))

    assert result == {"status": "ok"}
    assert db.commit_called is False


def test_rejects_unsafe_jwt_algorithm():
    with pytest.raises(ValidationError, match="JWT_ALGORITHM"):
        Settings(JWT_ALGORITHM="none")

def test_development_otp_disclosure_is_disabled_by_default():
    settings = Settings(ENV="development")
    assert settings.DEV_OTP_ENABLED is False


def test_production_rejects_development_otp_disclosure():
    with pytest.raises(ValidationError, match="DEV_OTP_ENABLED"):
        Settings(
            ENV="production",
            DEV_OTP_ENABLED=True,
            JWT_SECRET="a" * 40,
            DATABASE_URL="postgresql://user:password@db:5432/solix",
            ALLOWED_ORIGINS=["https://solix.example.com"],
        )


def test_otp_request_only_returns_dev_otp_when_explicitly_enabled(monkeypatch):
    import app.routers.auth as auth_router
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "ENV", "development")
    monkeypatch.setattr(app_settings, "DEV_OTP_ENABLED", False)
    monkeypatch.setattr(auth_router, "generate_otp", lambda email: "123456")
    monkeypatch.setattr(auth_router, "send_otp_via_email_or_sms", lambda email, otp: None)

    response = auth_router.request_otp(auth_router.OtpRequestBody(email="otp-guard@example.com"))
    assert "dev_otp" not in response

    monkeypatch.setattr(app_settings, "DEV_OTP_ENABLED", True)
    response = auth_router.request_otp(auth_router.OtpRequestBody(email="otp-guard-enabled@example.com"))
    assert response["dev_otp"] == "123456"
