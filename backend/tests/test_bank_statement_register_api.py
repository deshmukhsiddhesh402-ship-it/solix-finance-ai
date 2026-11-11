"""Tenant-scoped bank statement register API regression tests."""
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


def test_bank_statement_register_masks_account_number_and_scopes_tenant():
    from app.routers.banking import list_bank_statements

    org_id = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        bank_name="Example Bank",
        account_no="001234567890",
        txn_date=date(2026, 11, 10),
        description="Supplier payment",
        amount=Decimal("12500.00"),
        txn_type="debit",
        mode="NEFT",
        reconciled=False,
        matched_journal_id=None,
    )
    db = FakeDB([row], total=1)

    result = list_bank_statements(
        org_id=str(org_id),
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 30),
        txn_type="debit",
        reconciled=False,
        limit=25,
        offset=0,
        db=db,
        _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["statements"][0]["account_no_masked"] == "****7890"
    assert "001234567890" not in str(result)
    assert result["statements"][0]["amount"] == 12500.0
    assert any("bank_statements.org_id" in str(item) for item in db.rows_query.filters)
    assert any("bank_statements.org_id" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 25
    assert db.rows_query.offset_value == 0
    assert len(db.rows_query.ordering) == 2


def test_bank_statement_register_masks_short_account_numbers_fully():
    from app.routers.banking import list_bank_statements

    row = SimpleNamespace(
        id=uuid4(), bank_name="Example Bank", account_no="123",
        txn_date=date(2026, 11, 10), description=None, amount=Decimal("10.00"),
        txn_type="credit", mode=None, reconciled=True, matched_journal_id=None,
    )
    result = list_bank_statements(
        org_id=str(uuid4()), start_date=None, end_date=None, txn_type=None,
        reconciled=None, limit=50, offset=0, db=FakeDB([row], 1), _user=str(uuid4()),
    )

    assert result["statements"][0]["account_no_masked"] == "****"


def test_bank_statement_register_rejects_reversed_date_range_before_queries():
    from app.routers.banking import list_bank_statements

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_bank_statements(
            org_id=str(uuid4()), start_date=date(2026, 11, 30),
            end_date=date(2026, 11, 1), txn_type=None, reconciled=None,
            limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_bank_statement_register_rejects_invalid_organization_before_queries():
    from app.routers.banking import list_bank_statements

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_bank_statements(
            org_id="not-a-uuid", start_date=None, end_date=None, txn_type=None,
            reconciled=None, limit=50, offset=0, db=db, _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
