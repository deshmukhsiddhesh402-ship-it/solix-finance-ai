"""Organization-scoped membership register API regression tests."""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeQuery:
    def __init__(self, rows=None, scalar_value=None):
        self.rows = rows or []
        self.scalar_value = scalar_value
        self.filters = []
        self.ordering = []
        self.offset_value = None
        self.limit_value = None
        self.join_args = []

    def join(self, *args):
        self.join_args.extend(args)
        return self

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, *ordering):
        self.ordering.extend(ordering)
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows

    def scalar(self):
        return self.scalar_value


class FakeDB:
    def __init__(self, rows, total):
        self.memberships_query = FakeQuery(rows)
        self.count_query = FakeQuery(scalar_value=total)
        self.queries = []

    def query(self, *entities):
        self.queries.append(entities)
        if len(entities) == 1 and getattr(entities[0], "name", None) == "count":
            return self.count_query
        return self.memberships_query


def test_membership_register_returns_user_details_with_tenant_scope():
    from app.routers.enterprise import list_memberships

    org_id = uuid4()
    membership = SimpleNamespace(
        id=uuid4(),
        role="accountant",
        created_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )
    user = SimpleNamespace(
        id=uuid4(),
        email="accountant@example.com",
        full_name="Finance User",
    )
    db = FakeDB([(membership, user)], total=1)

    result = list_memberships(
        org_id=str(org_id),
        limit=25,
        offset=0,
        db=db,
        _acting_user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["memberships"][0]["email"] == "accountant@example.com"
    assert result["memberships"][0]["role"] == "accountant"
    assert any("org_memberships.org_id" in str(item) for item in db.memberships_query.filters)
    assert any("org_memberships.org_id" in str(item) for item in db.count_query.filters)
    assert db.memberships_query.limit_value == 25
    assert db.memberships_query.offset_value == 0
    assert len(db.memberships_query.ordering) == 2


def test_membership_register_rejects_invalid_organization_identifier():
    from app.routers.enterprise import list_memberships

    db = FakeDB([], total=0)
    with pytest.raises(HTTPException) as exc:
        list_memberships(
            org_id="invalid",
            limit=50,
            offset=0,
            db=db,
            _acting_user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries


def test_membership_register_returns_empty_page_for_empty_organization():
    from app.routers.enterprise import list_memberships

    db = FakeDB([], total=0)
    result = list_memberships(
        org_id=str(uuid4()),
        limit=50,
        offset=0,
        db=db,
        _acting_user=str(uuid4()),
    )

    assert result == {"memberships": [], "total": 0, "limit": 50, "offset": 0}
