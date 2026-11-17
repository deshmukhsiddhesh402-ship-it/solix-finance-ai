"""Regression tests for soft-archiving fixed assets."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeQuery:
    def __init__(self, item):
        self.item = item
        self.filters = []
        self.for_update = False

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def with_for_update(self):
        self.for_update = True
        return self

    def first(self):
        return self.item


class FakeDB:
    def __init__(self, item):
        self.query_result = FakeQuery(item)
        self.added = []
        self.committed = False
        self.rolled_back = False

    def query(self, model):
        return self.query_result

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_archive_fixed_asset_is_soft_and_audited():
    from app.models.enterprise import AuditLog
    from app.routers.accounting import archive_fixed_asset

    asset_id, org_id, user_id = uuid4(), uuid4(), uuid4()
    asset = SimpleNamespace(id=asset_id, org_id=org_id, is_active=True)
    db = FakeDB(asset)
    result = archive_fixed_asset(
        asset_id=str(asset_id), org_id=str(org_id), db=db, _user=str(user_id)
    )
    audit = next(value for value in db.added if isinstance(value, AuditLog))

    assert asset.is_active is False
    assert result["is_active"] is False
    assert audit.action == "archive"
    assert audit.entity_type == "fixed_asset"
    assert audit.changes == {"is_active": {"old": True, "new": False}}
    assert db.query_result.for_update is True
    assert any("fixed_assets.org_id" in str(value) for value in db.query_result.filters)
    assert db.committed is True
    assert db.rolled_back is False


def test_archive_fixed_asset_does_not_disclose_foreign_tenant():
    from app.routers.accounting import archive_fixed_asset

    db = FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        archive_fixed_asset(
            asset_id=str(uuid4()), org_id=str(uuid4()), db=db, _user=str(uuid4())
        )
    assert exc.value.status_code == 404
    assert db.rolled_back is True
    assert db.added == []


def test_archive_fixed_asset_is_idempotent():
    from app.routers.accounting import archive_fixed_asset

    asset = SimpleNamespace(id=uuid4(), org_id=uuid4(), is_active=False)
    db = FakeDB(asset)
    result = archive_fixed_asset(
        asset_id=str(asset.id), org_id=str(asset.org_id), db=db, _user=str(uuid4())
    )
    assert result["is_active"] is False
    assert db.added == []
    assert db.committed is False
    assert db.rolled_back is True


def test_archive_fixed_asset_requires_admin_delete_permission():
    from app.routers.accounting import router

    route = next(route for route in router.routes if getattr(route, "path", None) == "/fixed-assets/{asset_id}/archive")
    dependency = next(
        dependency.call for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    assert (closure["resource"], closure["action"]) == ("fixed_assets", "delete")


def test_fixed_asset_model_defaults_to_active():
    from app.models.accounting import FixedAsset

    column = FixedAsset.__table__.c.is_active
    assert column.nullable is False
    assert column.default.arg is True
    assert column.server_default is not None


def test_fixed_asset_archive_migration_preserves_existing_rows():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "013_fixed_asset_active_status.sql"
    ).read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE" in migration
