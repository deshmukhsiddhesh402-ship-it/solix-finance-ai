"""Regression tests for bounded API-key listing."""

from pathlib import Path
import sys
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.enterprise import ApiKey
from app.routers.enterprise import list_api_keys


class FakeQuery:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.limit_value = None
        self.ordered = False

    def filter(self, *criteria):
        return self

    def order_by(self, *args):
        self.ordered = True
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, query):
        self.query_obj = query

    def query(self, model):
        assert model is ApiKey
        return self.query_obj


def test_api_key_listing_applies_default_limit_and_ordering():
    org_id = uuid4()
    query = FakeQuery()
    response = list_api_keys(org_id=str(org_id), db=FakeDB(query), _user=str(uuid4()))

    assert response == {"keys": []}
    assert query.limit_value == 50
    assert query.ordered


def test_api_key_listing_accepts_explicit_limit():
    org_id = uuid4()
    query = FakeQuery()
    list_api_keys(
        org_id=str(org_id),
        limit=200,
        db=FakeDB(query),
        _user=str(uuid4()),
    )

    assert query.limit_value == 200
