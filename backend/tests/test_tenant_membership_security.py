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
