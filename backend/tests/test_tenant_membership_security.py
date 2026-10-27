"""Regression tests for tenant membership fail-closed behavior."""
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import OrgMembership
from app.services.tenant_membership import require_exactly_one_membership


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.requested_limit = None

    def limit(self, value):
        self.requested_limit = value
        return self

    def all(self):
        return self.rows[: self.requested_limit]


def _require(rows):
    return require_exactly_one_membership(
        FakeQuery(rows),
        missing_detail="membership missing",
        ambiguous_detail="membership ambiguous",
    )


def test_missing_membership_fails_closed():
    with pytest.raises(HTTPException) as exc:
        _require([])
    assert exc.value.status_code == 403
    assert exc.value.detail == "membership missing"


def test_exactly_one_membership_is_accepted():
    row = object()
    assert _require([row]) is row


def test_duplicate_membership_fails_closed():
    with pytest.raises(HTTPException) as exc:
        _require([object(), object(), object()])
    assert exc.value.status_code == 403
    assert exc.value.detail == "membership ambiguous"


def test_membership_query_is_capped_to_two_rows():
    query = FakeQuery([object(), object(), object()])
    with pytest.raises(HTTPException):
        require_exactly_one_membership(
            query,
            missing_detail="membership missing",
            ambiguous_detail="membership ambiguous",
        )
    assert query.requested_limit == 2


def test_membership_model_declares_user_organization_uniqueness():
    constraints = [
        constraint
        for constraint in OrgMembership.__table__.constraints
        if getattr(constraint, "name", None) == "uq_org_memberships_user_org"
    ]
    assert len(constraints) == 1
    assert {column.name for column in constraints[0].columns} == {"user_id", "org_id"}


def test_permission_dependency_denies_duplicate_memberships(monkeypatch):
    from uuid import uuid4
    import app.routers.enterprise as enterprise_router
    from app.models.auth_user import User

    user_id, org_id = uuid4(), uuid4()
    user = User(
        id=user_id,
        org_id=org_id,
        email="tenant-check@example.com",
        full_name="Tenant Check",
        auth_provider="otp",
        role="owner",
    )
    duplicate_rows = [
        OrgMembership(user_id=user_id, org_id=org_id, role="admin"),
        OrgMembership(user_id=user_id, org_id=org_id, role="auditor"),
    ]

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *criteria):
            return self

        def first(self):
            return user if self.model is User else None

        def limit(self, value):
            assert value == 2
            return self

        def all(self):
            return duplicate_rows if self.model is OrgMembership else []

    class DB:
        def query(self, model):
            return Query(model)

    monkeypatch.setattr(enterprise_router, "decode_access_token", lambda token: {"sub": str(user_id)})
    dependency = enterprise_router.require_permission("api_keys", "view")

    with pytest.raises(HTTPException) as exc:
        dependency(org_id=str(org_id), authorization="Bearer test-token", db=DB())

    assert exc.value.status_code == 403
    assert "ambiguous" in exc.value.detail

def test_permission_dependency_denies_user_without_membership_in_requested_org(monkeypatch):
    """A valid user token must not authorize access to an unrelated organization."""
    from uuid import uuid4
    import app.routers.enterprise as enterprise_router
    from app.models.auth_user import User

    user_id, requested_org_id = uuid4(), uuid4()
    user = User(
        id=user_id,
        org_id=uuid4(),  # Legacy/default organization is not sufficient authorization.
        email="cross-tenant-check@example.com",
        full_name="Cross Tenant Check",
        auth_provider="otp",
        role="owner",
    )

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *criteria):
            return self

        def first(self):
            return user if self.model is User else None

        def limit(self, value):
            assert value == 2
            return self

        def all(self):
            # No OrgMembership exists for the requested organization.
            return []

    class DB:
        def query(self, model):
            return Query(model)

    monkeypatch.setattr(
        enterprise_router, "decode_access_token",
        lambda token: {"sub": str(user_id)},
    )
    dependency = enterprise_router.require_permission("reports", "view")

    with pytest.raises(HTTPException) as exc:
        dependency(
            org_id=str(requested_org_id),
            authorization="Bearer valid-looking-token",
            db=DB(),
        )

    assert exc.value.status_code == 403
    assert "not a member" in exc.value.detail

def test_permission_dependency_rejects_membership_for_different_tenant(monkeypatch):
    """A mismatched membership row must never authorize the requested tenant."""
    from uuid import uuid4
    import app.routers.enterprise as enterprise_router
    from app.models.auth_user import User

    user_id, requested_org_id = uuid4(), uuid4()
    wrong_org_id = uuid4()
    user = User(
        id=user_id,
        org_id=requested_org_id,
        email="membership-scope-check@example.com",
        full_name="Membership Scope Check",
        auth_provider="otp",
        role="owner",
    )
    mismatched_membership = OrgMembership(
        user_id=user_id, org_id=wrong_org_id, role="admin"
    )

    class Query:
        def __init__(self, model):
            self.model = model

        def filter(self, *criteria):
            return self

        def first(self):
            return user if self.model is User else None

        def limit(self, value):
            assert value == 2
            return self

        def all(self):
            return [mismatched_membership] if self.model is OrgMembership else []

    class DB:
        def query(self, model):
            return Query(model)

    monkeypatch.setattr(
        enterprise_router, "decode_access_token",
        lambda token: {"sub": str(user_id)},
    )
    monkeypatch.setattr(
        enterprise_router, "has_permission",
        lambda *args: pytest.fail("RBAC must not run for a mismatched membership"),
    )
    dependency = enterprise_router.require_permission("api_keys", "view")

    with pytest.raises(HTTPException) as exc:
        dependency(
            org_id=str(requested_org_id),
            authorization="Bearer test-token",
            db=DB(),
        )

    assert exc.value.status_code == 403
    assert "does not match" in exc.value.detail

