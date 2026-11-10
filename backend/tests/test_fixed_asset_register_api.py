"""Tenant-scoped fixed asset register API regression tests."""
from datetime import date
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


def test_fixed_asset_register_returns_tenant_filtered_asset_values():
    from app.routers.accounting import list_fixed_assets

    org_id = uuid4()
    asset = SimpleNamespace(
        id=uuid4(),
        asset_name="Delivery Vehicle",
        purchase_date=date(2026, 4, 1),
        cost=Decimal("800000.00"),
        salvage_value=Decimal("50000.00"),
        useful_life_years=8,
        depreciation_method="wdv",
    )
    db = FakeDB([asset], total=1)

    result = list_fixed_assets(
        org_id=str(org_id),
        purchase_date_from=date(2026, 1, 1),
        purchase_date_to=date(2026, 12, 31),
        depreciation_method="wdv",
        limit=20,
        offset=0,
        db=db,
        _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["assets"][0]["cost"] == 800000.0
    assert result["assets"][0]["salvage_value"] == 50000.0
    assert result["assets"][0]["depreciation_method"] == "wdv"
    assert any("fixed_assets.org_id" in str(item) for item in db.rows_query.filters)
    assert any("fixed_assets.org_id" in str(item) for item in db.count_query.filters)
    assert any("fixed_assets.depreciation_method" in str(item) for item in db.rows_query.filters)
    assert db.rows_query.limit_value == 20
    assert db.rows_query.offset_value == 0
    assert len(db.rows_query.ordering) == 3


def test_fixed_asset_register_rejects_reversed_purchase_date_range():
    from app.routers.accounting import list_fixed_assets

    db = FakeDB([], total=0)
    with pytest.raises(HTTPException) as exc:
        list_fixed_assets(
            org_id=str(uuid4()),
            purchase_date_from=date(2026, 12, 31),
            purchase_date_to=date(2026, 1, 1),
            depreciation_method=None,
            limit=50,
            offset=0,
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_fixed_asset_register_rejects_invalid_organization_identifier():
    from app.routers.accounting import list_fixed_assets

    db = FakeDB([], total=0)
    with pytest.raises(HTTPException) as exc:
        list_fixed_assets(
            org_id="invalid",
            purchase_date_from=None,
            purchase_date_to=None,
            depreciation_method=None,
            limit=50,
            offset=0,
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
