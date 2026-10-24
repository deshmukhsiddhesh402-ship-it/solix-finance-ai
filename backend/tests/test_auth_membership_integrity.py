"""OTP login must fail closed when tenant membership is ambiguous."""
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.routers.auth as auth_router
from app.models.auth_user import OrgMembership, User


class _Query:
    def __init__(self, model, user, memberships):
        self.model = model
        self.user = user
        self.memberships = memberships
        self.criteria = ()

    def filter(self, *criteria):
        self.criteria = criteria
        return self

    def all(self):
        if self.model is not OrgMembership:
            return []
        return [
            membership for membership in self.memberships
            if all(
                (criterion.left.name == "user_id" and criterion.right.value == membership.user_id)
                or (criterion.left.name == "org_id" and criterion.right.value == membership.org_id)
                for criterion in self.criteria
            )
        ]

    def first(self):
        if self.model is User:
            return self.user
        matches = self.all()
        return matches[0] if matches else None


class _DB:
    def __init__(self, user, memberships):
        self.user = user
        self.memberships = memberships

    def query(self, model):
        return _Query(model, self.user, self.memberships)


def _login(monkeypatch, user, memberships):
    monkeypatch.setattr(auth_router, "verify_otp", lambda email, otp: True)
    monkeypatch.setattr(auth_router, "create_access_token", lambda subject: "test-token")
    return auth_router.verify_otp_endpoint(
        auth_router.OtpVerifyBody(email=user.email, otp="123456"),
        _DB(user, memberships),
    )


def test_otp_login_rejects_duplicate_memberships(monkeypatch):
    user_id, org_id = uuid4(), uuid4()
    user = User(
        id=user_id, org_id=org_id, email="member@example.com",
        full_name="Member", auth_provider="otp", role="owner",
    )
    memberships = [
        OrgMembership(user_id=user_id, org_id=org_id, role="admin"),
        OrgMembership(user_id=user_id, org_id=org_id, role="auditor"),
    ]

    with pytest.raises(HTTPException) as exc:
        _login(monkeypatch, user, memberships)

    assert exc.value.status_code == 403
    assert exc.value.detail == "User tenant membership is missing or ambiguous."


def test_otp_login_rejects_membership_for_another_tenant(monkeypatch):
    user_id, org_id, other_org_id = uuid4(), uuid4(), uuid4()
    user = User(
        id=user_id, org_id=org_id, email="member@example.com",
        full_name="Member", auth_provider="otp", role="owner",
    )
    membership = OrgMembership(user_id=user_id, org_id=other_org_id, role="admin")

    with pytest.raises(HTTPException) as exc:
        _login(monkeypatch, user, [membership])

    assert exc.value.status_code == 403
    assert exc.value.detail == "User tenant membership is missing or ambiguous."


def test_otp_login_accepts_exactly_one_matching_membership(monkeypatch):
    user_id, org_id = uuid4(), uuid4()
    user = User(
        id=user_id, org_id=org_id, email="member@example.com",
        full_name="Member", auth_provider="otp", role="owner",
    )
    membership = OrgMembership(user_id=user_id, org_id=org_id, role="admin")

    response = _login(monkeypatch, user, [membership])

    assert response["access_token"] == "test-token"
    assert response["user_id"] == str(user_id)
    assert response["org_id"] == str(org_id)
