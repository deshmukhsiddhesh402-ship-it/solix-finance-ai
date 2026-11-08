"""Regression tests for organization membership lifecycle audit events."""
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.auth_user import User
from app.models.enterprise import AuditLog, OrgMembership
from app.routers import enterprise


class FakeQuery:
    def __init__(self, first_result=None, rows=None):
        self.first_result = first_result
        self.rows = rows or []
        self.limit_value = None

    def filter(self, *criteria):
        return self

    def first(self):
        return self.first_result

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows[: self.limit_value]


class FakeDB:
    def __init__(self, user, memberships=None):
        self.user = user
        self.memberships = memberships or []
        self.added = []
        self.flush_count = 0
        self.commit_count = 0

    def query(self, model):
        if model is User:
            return FakeQuery(first_result=self.user)
        if model is OrgMembership:
            return FakeQuery(rows=self.memberships)
        raise AssertionError(f"Unexpected model: {model}")

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.flush_count += 1
        for row in self.added:
            if isinstance(row, OrgMembership) and row.id is None:
                row.id = uuid4()

    def commit(self):
        self.commit_count += 1


def _audit_rows(db):
    return [row for row in db.added if isinstance(row, AuditLog)]


def test_membership_creation_records_safe_audit_metadata_in_same_transaction():
    org_id, actor_id, target_id = uuid4(), uuid4(), uuid4()
    target_user = User(
        id=target_id,
        email="new-member@example.com",
        full_name="New Member",
        auth_provider="otp",
        role="member",
    )
    db = FakeDB(target_user)

    response = enterprise.add_membership(
        enterprise.AddMembershipRequest(
            org_id=str(org_id),
            user_email="new-member@example.com",
            role="accountant",
        ),
        org_id=str(org_id),
        db=db,
        _acting_user=str(actor_id),
    )

    membership_rows = [row for row in db.added if isinstance(row, OrgMembership)]
    audit_rows = _audit_rows(db)
    assert response["message"].endswith("added to organization as accountant.")
    assert len(membership_rows) == 1
    assert len(audit_rows) == 1
    assert db.flush_count == 1
    assert db.commit_count == 1

    membership = membership_rows[0]
    audit = audit_rows[0]
    assert audit.org_id == org_id
    assert audit.user_id == actor_id
    assert audit.action == "create"
    assert audit.entity_type == "org_membership"
    assert audit.entity_id == str(membership.id)
    assert audit.changes == {
        "user_id": {"before": None, "after": str(target_id)},
        "role": {"before": None, "after": "accountant"},
    }
    assert "new-member@example.com" not in repr(audit.changes)


def test_existing_membership_does_not_create_duplicate_audit_event():
    org_id, actor_id, target_id = uuid4(), uuid4(), uuid4()
    target_user = User(
        id=target_id,
        email="existing-member@example.com",
        full_name="Existing Member",
        auth_provider="otp",
        role="member",
    )
    existing = OrgMembership(
        id=uuid4(), user_id=target_id, org_id=org_id, role="auditor"
    )
    db = FakeDB(target_user, memberships=[existing])

    with pytest.raises(HTTPException) as exc:
        enterprise.add_membership(
            enterprise.AddMembershipRequest(
                org_id=str(org_id),
                user_email="existing-member@example.com",
                role="accountant",
            ),
            org_id=str(org_id),
            db=db,
            _acting_user=str(actor_id),
        )

    assert exc.value.status_code == 409
    assert db.added == []
    assert db.flush_count == 0
    assert db.commit_count == 0
    assert _audit_rows(db) == []
