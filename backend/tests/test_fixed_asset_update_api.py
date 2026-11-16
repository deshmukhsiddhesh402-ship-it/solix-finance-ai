"""Regression tests for tenant-scoped fixed asset updates."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError


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


def _payload(**overrides):
    from app.routers.accounting import FixedAssetUpdate

    return FixedAssetUpdate(**overrides)


def test_fixed_asset_update_locks_tenant_row_and_audits_changes():
    from app.models.enterprise import AuditLog
    from app.routers.accounting import update_fixed_asset

    asset_id, org_id, user_id = uuid4(), uuid4(), uuid4()
    asset = SimpleNamespace(
        id=asset_id, org_id=org_id, asset_name="Vehicle",
        purchase_date=date(2026, 1, 1), cost=Decimal("800000.00"),
        salvage_value=Decimal("50000.00"), useful_life_years=8,
        depreciation_method="wdv",
    )
    db = FakeDB(asset)
    result = update_fixed_asset(
        asset_id=str(asset_id), payload=_payload(asset_name=" Delivery Vehicle "),
        org_id=str(org_id), db=db, _user=str(user_id),
    )
    audit = next(value for value in db.added if isinstance(value, AuditLog))

    assert result["asset_name"] == "Delivery Vehicle"
    assert asset.asset_name == "Delivery Vehicle"
    assert audit.action == "edit"
    assert audit.entity_type == "fixed_asset"
    assert audit.changes == {"asset_name": {"old": "Vehicle", "new": "Delivery Vehicle"}}
    assert db.query_result.for_update is True
    assert any("fixed_assets.org_id" in str(value) for value in db.query_result.filters)
    assert db.committed is True
    assert db.rolled_back is False


def test_fixed_asset_update_rejects_salvage_value_above_final_cost():
    from app.routers.accounting import update_fixed_asset

    asset_id, org_id = uuid4(), uuid4()
    asset = SimpleNamespace(
        id=asset_id, org_id=org_id, asset_name="Vehicle",
        purchase_date=date(2026, 1, 1), cost=Decimal("800000.00"),
        salvage_value=Decimal("50000.00"), useful_life_years=8,
        depreciation_method="wdv",
    )
    db = FakeDB(asset)
    with pytest.raises(HTTPException) as exc:
        update_fixed_asset(
            asset_id=str(asset_id), payload=_payload(cost=Decimal("40000.00")),
            org_id=str(org_id), db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 422
    assert asset.cost == Decimal("800000.00")
    assert db.rolled_back is True
    assert db.committed is False


def test_fixed_asset_update_allows_consistent_cost_and_salvage_change_together():
    from app.routers.accounting import update_fixed_asset

    asset_id, org_id = uuid4(), uuid4()
    asset = SimpleNamespace(
        id=asset_id, org_id=org_id, asset_name="Vehicle",
        purchase_date=date(2026, 1, 1), cost=Decimal("800000.00"),
        salvage_value=Decimal("50000.00"), useful_life_years=8,
        depreciation_method="wdv",
    )
    db = FakeDB(asset)
    result = update_fixed_asset(
        asset_id=str(asset_id),
        payload=_payload(cost=Decimal("40000.00"), salvage_value=Decimal("1000.00")),
        org_id=str(org_id), db=db, _user=str(uuid4()),
    )
    assert result["cost"] == "40000.00"
    assert result["salvage_value"] == "1000.00"
    assert db.committed is True


def test_fixed_asset_update_does_not_disclose_foreign_tenant():
    from app.routers.accounting import update_fixed_asset

    db = FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        update_fixed_asset(
            asset_id=str(uuid4()), payload=_payload(asset_name="New"),
            org_id=str(uuid4()), db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 404
    assert db.rolled_back is True
    assert db.added == []


@pytest.mark.parametrize("data", [{}, {"asset_name": None}, {"cost": True}, {"salvage_value": True}, {"useful_life_years": True}])
def test_fixed_asset_update_rejects_empty_null_and_boolean_values(data):
    with pytest.raises(ValidationError):
        _payload(**data)


def test_fixed_asset_update_requires_fixed_asset_edit_permission():
    from app.routers.accounting import router

    route = next(route for route in router.routes if getattr(route, "path", None) == "/fixed-assets/{asset_id}")
    dependency = next(
        dependency.call for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    assert (closure["resource"], closure["action"]) == ("fixed_assets", "edit")
