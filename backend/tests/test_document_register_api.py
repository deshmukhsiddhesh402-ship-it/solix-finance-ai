"""Tenant-scoped document register regression tests."""
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


def test_document_register_scopes_tenant_and_omits_storage_paths():
    from app.routers.chat import list_documents

    row = SimpleNamespace(
        id=uuid4(), file_name="bank-statement.pdf", file_type="pdf",
        uploaded_by=uuid4(),
        created_at=datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc),
        storage_path="private/bucket/secret-key-location",
    )
    db = FakeDB([row], 1)

    result = list_documents(
        org_id=str(uuid4()), file_type="PDF", limit=20, offset=0,
        db=db, user_id=str(uuid4()),
    )

    assert result["total"] == 1
    assert result["documents"][0]["file_name"] == "bank-statement.pdf"
    assert "storage_path" not in result["documents"][0]
    assert "secret-key-location" not in str(result)
    assert any("documents.org_id" in str(item) for item in db.rows_query.filters)
    assert any("documents.org_id" in str(item) for item in db.count_query.filters)
    assert db.rows_query.limit_value == 20
    assert db.rows_query.offset_value == 0
    assert len(db.rows_query.ordering) == 2


def test_document_register_rejects_invalid_tenant_or_user_before_queries():
    from app.routers.chat import list_documents

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_documents(
            org_id="bad-org", file_type=None, limit=50, offset=0,
            db=db, user_id=str(uuid4()),
        )

    assert exc.value.status_code == 400
    assert not db.queries

    with pytest.raises(HTTPException) as exc:
        list_documents(
            org_id=str(uuid4()), file_type=None, limit=50, offset=0,
            db=db, user_id="bad-user",
        )

    assert exc.value.status_code == 400
    assert not db.queries


def test_document_register_rejects_blank_file_type_before_queries():
    from app.routers.chat import list_documents

    db = FakeDB([], 0)
    with pytest.raises(HTTPException) as exc:
        list_documents(
            org_id=str(uuid4()), file_type="   ", limit=50, offset=0,
            db=db, user_id=str(uuid4()),
        )

    assert exc.value.status_code == 422
    assert not db.queries
