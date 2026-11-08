"""Race-condition tests for organization membership creation."""
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

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

    def filter(self, *criteria):
        return self

    def limit(self, value):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.first_result if self.first_result is not None else (
            self.rows[0] if self.rows else None
        )


class ConflictDB:
    def __init__(self, user, concurrent_membership, fail_at):
        self.user = user
        self.concurrent_membership = concurrent_membership
        self.fail_at = fail_at
        self.added = []
        self.rolled_back_rows = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.rolled_back = False

    def query(self, model):
        if model is User:
            return FakeQuery(first_result=self.user)
        if model is OrgMembership:
            if self.rolled_back:
                return FakeQuery(first_result=self.concurrent_membership)
            return FakeQuery(rows=[])
        raise AssertionError(f"Unexpected model: {model}")

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.flush_count += 1
        if self.fail_at == "flush":
            raise IntegrityError("INSERT", {}, RuntimeError("unique violation"))
        for row in self.added:
            if isinstance(row, OrgMembership) and row.id is None:
                row.id = uuid4()

    def commit(self):
        self.commit_count += 1
        if self.fail_at == "commit":
            raise IntegrityError("COMMIT", {}, RuntimeError("unique violation"))

    def rollback(self):
        self.rollback_count += 1
        self.rolled_back = True
        self.rolled_back_rows = list(self.added)
        self.added.clear()


def _request(org_id):
    return enterprise.AddMembershipRequest(
        org_id=str(org_id),
        user_email="race-member@example.com",
        role="accountant",
    )


@pytest.mark.parametrize("fail_at", ["flush", "commit"])
def test_concurrent_duplicate_membership_returns_409_and_rolls_back_audit(fail_at):
    org_id, actor_id, target_id = uuid4(), uuid4(), uuid4()
    user = User(
        id=target_id,
        email="race-member@example.com",
        full_name="Race Member",
        auth_provider="otp",
        role="member",
    )
    concurrent = OrgMembership(
        id=uuid4(), user_id=target_id, org_id=org_id, role="admin"
    )
    db = ConflictDB(user, concurrent, fail_at)

    with pytest.raises(HTTPException) as exc:
        enterprise.add_membership(
            _request(org_id),
            org_id=str(org_id),
            db=db,
            _acting_user=str(actor_id),
        )

    assert exc.value.status_code == 409
    assert exc.value.detail == "User is already a member of this organization."
    assert db.rollback_count == 1
    assert db.commit_count == (1 if fail_at == "commit" else 0)
    assert db.added == []
    if fail_at == "commit":
        assert any(isinstance(row, AuditLog) for row in db.rolled_back_rows)
    else:
        assert not any(isinstance(row, AuditLog) for row in db.rolled_back_rows)


def test_unrelated_integrity_failure_is_not_misreported_as_duplicate_membership():
    org_id, actor_id, target_id = uuid4(), uuid4(), uuid4()
    user = User(
        id=target_id,
        email="race-member@example.com",
        full_name="Race Member",
        auth_provider="otp",
        role="member",
    )
    db = ConflictDB(user, concurrent_membership=None, fail_at="flush")

    with pytest.raises(IntegrityError):
        enterprise.add_membership(
            _request(org_id),
            org_id=str(org_id),
            db=db,
            _acting_user=str(actor_id),
        )

    assert db.rollback_count == 1
    assert db.added == []
