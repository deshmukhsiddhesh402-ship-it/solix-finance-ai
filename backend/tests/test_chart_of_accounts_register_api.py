"""Tenant-scoped chart-of-accounts register API regression tests."""
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
        self.rows_query = FakeQuery(rows)
        self.count_query = FakeQuery(scalar_value=total)
        self.queries = []

    def query(self, *entities):
        self.queries.append(entities)
        if len(entities) == 1 and getattr(entities[0], "name", None) == "count":
            return self.count_query
        return self.rows_query


def test_chart_of_accounts_register_filters_tenant_type_and_inactive_rows():
    from app.routers.accounting import list_chart_of_accounts

    org_id = uuid4()
    account = SimpleNamespace(
        id=uuid4(),
        code="CASH-001",
        name="Cash at Bank",
        account_type="asset",
        parent_id=None,
        is_active=True,
    )
    db = FakeDB([account], total=1)

    result = list_chart_of_accounts(
        org_id=str(org_id),
        account_type="asset",
        include_inactive=False,
        limit=25,
        offset=50,
        db=db,
        _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["accounts"][0]["code"] == "CASH-001"
    assert result["accounts"][0]["is_active"] is True
    assert any("chart_of_accounts.org_id" in str(item) for item in db.rows_query.filters)
    assert any("chart_of_accounts.org_id" in str(item) for item in db.count_query.filters)
    assert any("chart_of_accounts.account_type" in str(item) for item in db.rows_query.filters)
    assert any("chart_of_accounts.is_active IS true" in str(item) for item in db.rows_query.filters)
    assert db.rows_query.limit_value == 25
    assert db.rows_query.offset_value == 50
    assert len(db.rows_query.ordering) == 3


def test_chart_of_accounts_can_include_inactive_rows_for_review():
    from app.routers.accounting import list_chart_of_accounts

    inactive = SimpleNamespace(
        id=uuid4(),
        code="OLD-001",
        name="Closed Bank Account",
        account_type="asset",
        parent_id=None,
        is_active=False,
    )
    db = FakeDB([inactive], total=1)

    result = list_chart_of_accounts(
        org_id=str(uuid4()),
        account_type=None,
        include_inactive=True,
        limit=50,
        offset=0,
        db=db,
        _user=str(uuid4()),
    )

    assert result["accounts"][0]["is_active"] is False
    assert not any("is_active" in str(item) for item in db.rows_query.filters)


def test_chart_of_accounts_register_rejects_invalid_organization_identifier():
    from app.routers.accounting import list_chart_of_accounts

    db = FakeDB([], total=0)
    with pytest.raises(HTTPException) as exc:
        list_chart_of_accounts(
            org_id="invalid",
            account_type=None,
            include_inactive=False,
            limit=50,
            offset=0,
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
