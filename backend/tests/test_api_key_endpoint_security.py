"""Regression tests for API-key endpoint tenant scoping and secret handling."""
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import ApiKey
from app.routers.enterprise import (
    CreateApiKeyRequest,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)
from app.services.api_key_engine import hash_api_key


class FakeQuery:
    def __init__(self, rows=None, first_result=None):
        self.rows = rows or []
        self.first_result = first_result
        self.criteria = []

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def order_by(self, *args):
        return self

    def limit(self, value):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.first_result


class FakeDB:
    def __init__(self, query):
        self.fake_query = query
        self.added = []
        self.committed = False

    def query(self, model):
        assert model is ApiKey
        return self.fake_query

    def add(self, row):
        row.id = row.id or uuid4()
        self.added.append(row)

    def commit(self):
        self.committed = True


def _criterion_columns(query):
    return {criterion.left.key: criterion.right.value for criterion in query.criteria}


def test_create_api_key_persists_hash_and_mask_not_plaintext():
    org_id = uuid4()
    query = FakeQuery()
    db = FakeDB(query)
    request = CreateApiKeyRequest(org_id=str(org_id), name="Accounting integration")

    response = create_api_key(request, org_id=str(org_id), db=db, _user=str(uuid4()))

    assert db.committed
    assert len(db.added) == 1
    stored = db.added[0]
    plaintext = response["plaintext_key"]

    assert stored.org_id == org_id
    assert stored.hashed_key == hash_api_key(plaintext)
    assert stored.hashed_key != plaintext
    assert stored.key_prefix_display != plaintext
    assert plaintext not in stored.key_prefix_display
    assert response["warning"]
    assert "plaintext_key" not in stored.__dict__


def test_list_api_keys_filters_by_requested_org_and_excludes_revoked():
    org_id = uuid4()
    row = ApiKey(
        id=uuid4(),
        org_id=org_id,
        name="Reporting",
        hashed_key="a" * 64,
        key_prefix_display="solix_abcd...wxyz",
        revoked=False,
    )
    query = FakeQuery(rows=[row])
    db = FakeDB(query)

    response = list_api_keys(org_id=str(org_id), db=db, _user=str(uuid4()))

    filters = _criterion_columns(query)
    assert filters["org_id"] == org_id
    assert filters["revoked"] is False
    assert len(response["keys"]) == 1
    assert response["keys"][0]["masked_key"] == row.key_prefix_display
    assert "hashed_key" not in response["keys"][0]
    assert "plaintext_key" not in response["keys"][0]


def test_revoke_api_key_query_is_scoped_to_key_and_requested_org():
    org_id, key_id = uuid4(), uuid4()
    query = FakeQuery(first_result=None)
    db = FakeDB(query)

    with pytest.raises(HTTPException) as exc:
        revoke_api_key(
            key_id=str(key_id),
            org_id=str(org_id),
            db=db,
            _user=str(uuid4()),
        )

    filters = _criterion_columns(query)
    assert filters["id"] == key_id
    assert filters["org_id"] == org_id
    assert exc.value.status_code == 404
    assert not db.committed
