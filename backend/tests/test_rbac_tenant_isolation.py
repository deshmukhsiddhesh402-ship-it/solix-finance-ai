"""Regression tests for organization-scoped RBAC authorization."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.routers.enterprise as enterprise
from app.models.auth_user import User
from app.models.enterprise import OrgMembership


class _FakeQuery:
    def __init__(self, model, user, memberships):
        self.model = model
        self.user = user
        self.memberships = memberships
        self.criteria = ()

    def filter(self, *criteria):
        self.criteria = criteria
        return self

    def first(self):
        if self.model is User:
            return self.user
        if self.model is OrgMembership:
            # Model the database's AND semantics for user_id + org_id filters.
            for membership in self.memberships:
                if all(
                    criterion.left.name == "user_id" and criterion.right.value == membership.user_id
                    or criterion.left.name == "org_id" and criterion.right.value == membership.org_id
                    for criterion in self.criteria
                ):
                    return membership
        return None


class _FakeDB:
    def __init__(self, user, memberships):
        self.user = user
        self.memberships = memberships

    def query(self, model):
        return _FakeQuery(model, self.user, self.memberships)


def _authorize(monkeypatch, *, requested_org, memberships, resource="reports", action="view"):
    user_id = uuid4()
    user = User(id=user_id, email="member@example.com", org_id=uuid4(), role="owner")
    monkeypatch.setattr(
        enterprise,
        "decode_access_token",
        lambda token: {"sub": str(user_id)} if token == "valid-token" else None,
    )
    dependency = enterprise.require_permission(resource, action)
    return dependency(
        org_id=str(requested_org),
        authorization="Bearer valid-token",
        db=_FakeDB(user, memberships),
    )


def test_membership_in_another_organization_does_not_authorize_access(monkeypatch):
    user_id = uuid4()
    requested_org = uuid4()
    other_org = uuid4()
    user = User(id=user_id, email="member@example.com", org_id=other_org, role="owner")
    membership = OrgMembership(user_id=user_id, org_id=other_org, role="admin")
    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: {"sub": str(user_id)})

    dependency = enterprise.require_permission("api_keys", "delete")
    with pytest.raises(HTTPException) as exc:
        dependency(
            org_id=str(requested_org),
            authorization="Bearer valid-token",
            db=_FakeDB(user, [membership]),
        )

    assert exc.value.status_code == 403


def test_role_is_resolved_for_the_requested_organization(monkeypatch):
    user_id = uuid4()
    org_a, org_b = uuid4(), uuid4()
    user = User(id=user_id, email="member@example.com", org_id=org_a, role="owner")
    memberships = [
        OrgMembership(user_id=user_id, org_id=org_a, role="admin"),
        OrgMembership(user_id=user_id, org_id=org_b, role="auditor"),
    ]
    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: {"sub": str(user_id)})
    dependency = enterprise.require_permission("api_keys", "delete")

    with pytest.raises(HTTPException) as exc:
        dependency(
            org_id=str(org_b),
            authorization="Bearer valid-token",
            db=_FakeDB(user, memberships),
        )

    assert exc.value.status_code == 403


def test_authorized_membership_allows_only_the_granted_permission(monkeypatch):
    user_id = uuid4()
    org_id = uuid4()
    user = User(id=user_id, email="member@example.com", org_id=org_id, role="owner")
    membership = OrgMembership(user_id=user_id, org_id=org_id, role="admin")
    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: {"sub": str(user_id)})

    dependency = enterprise.require_permission("api_keys", "delete")
    assert dependency(
        org_id=str(org_id),
        authorization="Bearer valid-token",
        db=_FakeDB(user, [membership]),
    ) == str(user_id)


def test_missing_or_invalid_bearer_token_fails_before_database_access(monkeypatch):
    user_id = uuid4()
    org_id = uuid4()
    user = User(id=user_id, email="member@example.com", org_id=org_id, role="owner")
    membership = OrgMembership(user_id=user_id, org_id=org_id, role="admin")
    db = _FakeDB(user, [membership])
    monkeypatch.setattr(enterprise, "decode_access_token", lambda token: None)
    dependency = enterprise.require_permission("reports", "view")

    for authorization in ("", "Basic valid-token", "Bearer invalid-token"):
        with pytest.raises(HTTPException) as exc:
            dependency(org_id=str(org_id), authorization=authorization, db=db)
        assert exc.value.status_code == 401
