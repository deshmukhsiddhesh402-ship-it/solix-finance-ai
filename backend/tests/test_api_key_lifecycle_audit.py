"""Regression tests for transactional API-key lifecycle audit events."""
from pathlib import Path
from uuid import uuid4
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import ApiKey, AuditLog
from app.routers import enterprise


class FakeQuery:
    def __init__(self, row):
        self.row = row

    def filter(self, *criteria):
        return self

    def first(self):
        return self.row


class FakeDB:
    def __init__(self, query_row=None):
        self.query_row = query_row
        self.added = []
        self.flush_count = 0
        self.commit_count = 0

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_count += 1
        for value in self.added:
            if isinstance(value, ApiKey) and value.id is None:
                value.id = uuid4()

    def commit(self):
        self.commit_count += 1

    def query(self, model):
        assert model is ApiKey
        return FakeQuery(self.query_row)


def _audit_rows(db):
    return [row for row in db.added if isinstance(row, AuditLog)]


def test_api_key_creation_records_safe_audit_metadata_in_same_transaction(monkeypatch):
    org_id = uuid4()
    user_id = uuid4()
    db = FakeDB()
    monkeypatch.setattr(enterprise, "generate_api_key", lambda: ("sk_live_plaintext", "secret_hash"))
    monkeypatch.setattr(enterprise, "mask_api_key", lambda value: "sk_live_...masked")

    result = enterprise.create_api_key(
        enterprise.CreateApiKeyRequest(org_id=str(org_id), name="Finance integration"),
        org_id=str(org_id),
        db=db,
        _user=str(user_id),
    )

    api_keys = [row for row in db.added if isinstance(row, ApiKey)]
    audit_rows = _audit_rows(db)

    assert result["plaintext_key"] == "sk_live_plaintext"
    assert len(api_keys) == 1
    assert len(audit_rows) == 1
    assert db.flush_count == 1
    assert db.commit_count == 1
    audit = audit_rows[0]
    assert audit.org_id == org_id
    assert audit.user_id == user_id
    assert audit.action == "create"
    assert audit.entity_type == "api_key"
    assert audit.entity_id == str(api_keys[0].id)
    assert audit.changes == {"name": {"before": None, "after": "Finance integration"}}
    assert "sk_live_plaintext" not in repr(audit.changes)
    assert "secret_hash" not in repr(audit.changes)


def test_api_key_revocation_records_only_the_state_transition():
    org_id = uuid4()
    user_id = uuid4()
    key_id = uuid4()
    key_row = SimpleNamespace(id=key_id, name="ERP integration", revoked=False)
    db = FakeDB(query_row=key_row)

    result = enterprise.revoke_api_key(
        key_id=str(key_id),
        org_id=str(org_id),
        db=db,
        _user=str(user_id),
    )

    audit_rows = _audit_rows(db)
    assert result == {"message": "API key revoked."}
    assert key_row.revoked is True
    assert len(audit_rows) == 1
    assert db.commit_count == 1
    audit = audit_rows[0]
    assert audit.action == "revoke"
    assert audit.entity_type == "api_key"
    assert audit.entity_id == str(key_id)
    assert audit.changes == {"revoked": {"before": False, "after": True}}


def test_repeated_api_key_revocation_does_not_create_duplicate_audit_event():
    org_id = uuid4()
    user_id = uuid4()
    key_id = uuid4()
    key_row = SimpleNamespace(id=key_id, name="ERP integration", revoked=True)
    db = FakeDB(query_row=key_row)

    result = enterprise.revoke_api_key(
        key_id=str(key_id),
        org_id=str(org_id),
        db=db,
        _user=str(user_id),
    )

    assert result == {"message": "API key revoked."}
    assert _audit_rows(db) == []
    assert db.commit_count == 1


def test_missing_api_key_does_not_create_audit_event():
    org_id = uuid4()
    user_id = uuid4()
    db = FakeDB(query_row=None)

    with pytest.raises(HTTPException) as exc:
        enterprise.revoke_api_key(
            key_id=str(uuid4()),
            org_id=str(org_id),
            db=db,
            _user=str(user_id),
        )

    assert exc.value.status_code == 404
    assert _audit_rows(db) == []
    assert db.commit_count == 0
