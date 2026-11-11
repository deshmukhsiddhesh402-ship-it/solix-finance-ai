"""Tenant-scoped GST return register regression tests."""
from datetime import datetime, timezone
from decimal import Decimal
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


def test_gst_return_register_scopes_tenant_and_filters_filing_period():
    from app.routers.tax import list_gst_returns

    org_id = uuid4()
    filed_at = datetime(2026, 11, 10, 9, 30, tzinfo=timezone.utc)
    row = SimpleNamespace(
        id=uuid4(), return_type="GSTR3B", period="2026-10",
        total_taxable_value=Decimal("100000.00"),
        total_tax_liability=Decimal("18000.00"), filed_at=filed_at,
    )
    db = FakeDB([row], 1)

    result = list_gst_returns(
        org_id=str(org_id), return_type="GSTR3B", period_from="2026-10",
        period_to="2026-10", filed=True, limit=20, offset=0,
        db=db, _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["returns"][0]["total_taxable_value"] == 100000.0
    assert result["returns"][0]["filed_at"] == filed_at.isoformat()
    assert any("gst_returns.org_id" in str(item) for item in db.rows_query.filters)
    assert any("gst_returns.org_id" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 20
    assert db.rows_query.offset_value == 0
    assert len(db.rows_query.ordering) == 3


@pytest.mark.parametrize("period", ["2026-00", "2026-13", "26-10", "2026-1", "2026-02-30"])
def test_gst_return_register_rejects_invalid_period(period):
    from app.routers.tax import list_gst_returns

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_gst_returns(
            org_id=str(uuid4()), return_type=None, period_from=period,
            period_to=None, filed=None, limit=50, offset=0,
            db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_gst_return_register_rejects_reversed_period_range():
    from app.routers.tax import list_gst_returns

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_gst_returns(
            org_id=str(uuid4()), return_type=None, period_from="2026-11",
            period_to="2026-10", filed=None, limit=50, offset=0,
            db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_gst_return_register_rejects_invalid_tenant_before_queries():
    from app.routers.tax import list_gst_returns

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_gst_returns(
            org_id="invalid", return_type=None, period_from=None,
            period_to=None, filed=None, limit=50, offset=0,
            db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
