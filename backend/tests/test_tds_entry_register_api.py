"""Tenant-scoped TDS entry register regression tests."""
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


def test_tds_entry_register_masks_valid_pan_and_scopes_tenant():
    from app.routers.tax import list_tds_entries

    row = SimpleNamespace(
        id=uuid4(), section="194C", deductee_name="Vendor One",
        deductee_pan="ABCDE1234F", amount_paid=Decimal("50000.00"),
        tds_rate=Decimal("1.00"), tds_amount=Decimal("500.00"),
        deposit_date=date(2026, 11, 7),
    )
    db = FakeDB([row], 1)

    result = list_tds_entries(
        org_id=str(uuid4()), section="194C", deposit_date_from="2026-11-01",
        deposit_date_to="2026-11-30", deposited=True, limit=20, offset=0,
        db=db, _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["entries"][0]["deductee_pan_masked"] == "*****1234F"
    assert "ABCDE1234F" not in str(result)
    assert result["entries"][0]["tds_amount"] == 500.0
    assert any("tds_entries.org_id" in str(item) for item in db.rows_query.filters)
    assert any("tds_entries.org_id" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 20
    assert db.rows_query.offset_value == 0
    assert len(db.rows_query.ordering) == 3


def test_tds_entry_register_hides_malformed_legacy_pan_entirely():
    from app.routers.tax import list_tds_entries

    row = SimpleNamespace(
        id=uuid4(), section="194J", deductee_name="Legacy Vendor",
        deductee_pan="BAD-PAN", amount_paid=Decimal("1000.00"),
        tds_rate=Decimal("10.00"), tds_amount=Decimal("100.00"), deposit_date=None,
    )
    result = list_tds_entries(
        org_id=str(uuid4()), section=None, deposit_date_from=None,
        deposit_date_to=None, deposited=None, limit=50, offset=0,
        db=FakeDB([row], 1), _user=str(uuid4()),
    )

    assert result["entries"][0]["deductee_pan_masked"] == "**********"
    assert "BAD-PAN" not in str(result)


@pytest.mark.parametrize("value", ["2026-02-30", "11-07-2026", "2026-1-01"])
def test_tds_entry_register_rejects_invalid_deposit_date(value):
    from app.routers.tax import list_tds_entries

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_tds_entries(
            org_id=str(uuid4()), section=None, deposit_date_from=value,
            deposit_date_to=None, deposited=None, limit=50, offset=0,
            db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_tds_entry_register_rejects_reversed_deposit_date_range():
    from app.routers.tax import list_tds_entries

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_tds_entries(
            org_id=str(uuid4()), section=None, deposit_date_from="2026-11-30",
            deposit_date_to="2026-11-01", deposited=None, limit=50, offset=0,
            db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries
