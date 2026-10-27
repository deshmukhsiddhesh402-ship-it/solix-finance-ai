"""Regression tests for consistent email identity in OTP authentication."""
from pathlib import Path
import sys
from uuid import uuid4

# Ensure the backend package is importable even if pytest is invoked from the repo root.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.routers.auth as auth_router
from app.models.auth_user import OrgMembership, User


def test_otp_request_normalizes_email_for_generation_and_delivery(monkeypatch):
    calls = {}
    monkeypatch.setattr(auth_router, "generate_otp", lambda email: (calls.update(generated_for=email) or "123456"))
    monkeypatch.setattr(auth_router, "send_otp_via_email_or_sms", lambda email, otp: calls.update(delivered_to=email, otp=otp))

    response = auth_router.request_otp(auth_router.OtpRequestBody(email="  Siddhesh@Example.com  "))

    assert calls["generated_for"] == "siddhesh@example.com"
    assert calls["delivered_to"] == "siddhesh@example.com"
    assert response["message"] == "If the address is eligible, an OTP will be sent."


def test_otp_verification_uses_normalized_email_for_account_lookup(monkeypatch):
    user_id = uuid4()
    org_id = uuid4()
    user = User(
        id=user_id,
        org_id=org_id,
        email="siddhesh@example.com",
        full_name="Siddhesh",
        auth_provider="otp",
        role="owner",
    )
    captured = {}

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def filter(self, *criteria):
            if self.model is User:
                captured["lookup_email"] = criteria[0].right.value
            return self

        def first(self):
            if self.model is User:
                return user
            return None

        def limit(self, value):
            return self

        def all(self):
            if self.model is OrgMembership:
                return [object()]
            return []

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

    monkeypatch.setattr(auth_router, "verify_otp", lambda email, otp: captured.update(verified_email=email) or True)
    monkeypatch.setattr(auth_router, "create_access_token", lambda subject: "test-token")

    response = auth_router.verify_otp_endpoint(
        auth_router.OtpVerifyBody(email="Siddhesh@Example.com", otp="123456"),
        FakeDB(),
    )

    assert captured["verified_email"] == "siddhesh@example.com"
    assert captured["lookup_email"] == "siddhesh@example.com"
    assert response["access_token"] == "test-token"
    assert response["user_id"] == str(user_id)
