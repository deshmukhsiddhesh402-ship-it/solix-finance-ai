"""Tenant-scoped journal register API regression tests."""
from datetime import date, datetime, timezone
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
        self.join_args = []

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

    def join(self, *args):
        self.join_args.extend(args)
        return self

    def all(self):
        return self.rows

    def scalar(self):
        return self.scalar_value


class FakeDB:
    def __init__(self, entries, line_rows, total):
        self.entries_query = FakeQuery(entries)
        self.lines_query = FakeQuery(line_rows)
        self.count_query = FakeQuery(scalar_value=total)
        self.queries = []

    def query(self, *entities):
        self.queries.append(entities)
        if len(entities) == 1 and getattr(entities[0], "name", None) == "count":
            return self.count_query
        if len(entities) == 1:
            return self.entries_query
        return self.lines_query


def test_journal_register_returns_scoped_entries_and_decimal_line_values():
    from app.models.accounting import ChartOfAccount, JournalEntry, JournalLine
    from app.routers.accounting import list_journal_entries

    org_id = uuid4()
    entry_id = uuid4()
    entry = SimpleNamespace(
        id=entry_id,
        entry_date=date(2026, 11, 10),
        narration="Customer invoice",
        reference_no="INV-100",
        created_at=datetime(2026, 11, 10, 9, 30, tzinfo=timezone.utc),
    )
    line = SimpleNamespace(
        journal_id=entry_id,
        debit=Decimal("1180.00"),
        credit=Decimal("0.00"),
        gst_rate_pct=Decimal("18.00"),
        gst_type="CGST",
        gst_taxable_value=Decimal("1000.00"),
        tds_section=None,
        tds_rate=None,
        tds_amount=None,
    )
    account = SimpleNamespace(name="Purchases", account_type="expense")
    db = FakeDB([entry], [(line, account)], total=1)

    result = list_journal_entries(
        org_id=str(org_id),
        start_date=date(2026, 11, 1),
        end_date=date(2026, 11, 30),
        limit=25,
        offset=0,
        db=db,
        _user=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["entries"][0]["id"] == str(entry_id)
    assert result["entries"][0]["lines"][0]["debit"] == 1180.0
    assert result["entries"][0]["lines"][0]["gst_rate_pct"] == 18.0
    assert any("journal_entries.org_id" in str(item) for item in db.entries_query.filters)
    assert any("journal_entries.org_id" in str(item) for item in db.count_query.filters)
    assert any("chart_of_accounts.org_id" in str(item) for item in db.lines_query.filters)
    assert db.entries_query.limit_value == 25
    assert db.entries_query.offset_value == 0
    assert len(db.entries_query.ordering) == 3


def test_journal_register_returns_empty_page_without_querying_lines():
    from app.routers.accounting import list_journal_entries

    db = FakeDB([], [], total=0)
    result = list_journal_entries(
        org_id=str(uuid4()),
        start_date=None,
        end_date=None,
        limit=50,
        offset=0,
        db=db,
        _user=str(uuid4()),
    )

    assert result == {"entries": [], "total": 0, "limit": 50, "offset": 0}
    assert len(db.queries) == 2


def test_journal_register_rejects_reversed_date_range_before_database_access():
    from app.routers.accounting import list_journal_entries

    db = FakeDB([], [], total=0)
    with pytest.raises(HTTPException) as exc:
        list_journal_entries(
            org_id=str(uuid4()),
            start_date=date(2026, 11, 30),
            end_date=date(2026, 11, 1),
            limit=50,
            offset=0,
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries


def test_journal_register_rejects_invalid_organization_identifier():
    from app.routers.accounting import list_journal_entries

    db = FakeDB([], [], total=0)
    with pytest.raises(HTTPException) as exc:
        list_journal_entries(
            org_id="not-a-uuid",
            start_date=None,
            end_date=None,
            limit=50,
            offset=0,
            db=db,
            _user=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries
