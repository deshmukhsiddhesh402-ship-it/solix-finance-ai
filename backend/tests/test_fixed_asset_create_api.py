"""Regression tests for tenant-scoped, audited fixed asset creation."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


class FakeDB:
    def __init__(self, fail_flush=False):
        self.added = []
        self.fail_flush = fail_flush
        self.committed = False
        self.rolled_back = False

    def add(self, value):
        self.added.append(value)
        if value.__class__.__name__ == "FixedAsset":
            value.id = uuid4()

    def flush(self):
        if self.fail_flush:
            raise IntegrityError("insert fixed asset", {}, Exception("constraint violation"))

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _payload(**overrides):
    from app.routers.accounting import FixedAssetCreate

    values = {
        "asset_name": " Delivery Vehicle ",
        "purchase_date": date(2026, 4, 1),
        "cost": Decimal("800000.00"),
        "salvage_value": Decimal("50000.00"),
        "useful_life_years": 8,
        "depreciation_method": "wdv",
    }
    values.update(overrides)
    return FixedAssetCreate(**values)


def test_fixed_asset_create_persists_tenant_values_and_audit_log():
    from app.models.enterprise import AuditLog
    from app.routers.accounting import create_fixed_asset

    org_id, user_id = uuid4(), uuid4()
    db = FakeDB()
    result = create_fixed_asset(
        payload=_payload(), org_id=str(org_id), db=db, _user=str(user_id)
    )
    asset = next(value for value in db.added if value.__class__.__name__ == "FixedAsset")
    audit = next(value for value in db.added if isinstance(value, AuditLog))

    assert result["asset_name"] == "Delivery Vehicle"
    assert result["cost"] == "800000.00"
    assert result["salvage_value"] == "50000.00"
    assert asset.org_id == org_id
    assert audit.org_id == org_id
    assert audit.user_id == user_id
    assert audit.entity_type == "fixed_asset"
    assert db.committed is True
    assert db.rolled_back is False


def test_fixed_asset_create_maps_database_constraint_failure():
    from app.routers.accounting import create_fixed_asset

    db = FakeDB(fail_flush=True)
    with pytest.raises(HTTPException) as exc:
        create_fixed_asset(
            payload=_payload(), org_id=str(uuid4()), db=db, _user=str(uuid4())
        )
    assert exc.value.status_code == 422
    assert db.rolled_back is True
    assert db.committed is False


@pytest.mark.parametrize("overrides", [
    {"asset_name": "   "},
    {"asset_name": "bad\nname"},
    {"cost": True},
    {"salvage_value": True},
    {"useful_life_years": True},
    {"salvage_value": Decimal("800000.01")},
    {"depreciation_method": "declining"},
])
def test_fixed_asset_create_rejects_invalid_values(overrides):
    with pytest.raises(ValidationError):
        _payload(**overrides)


def test_fixed_asset_create_rejects_invalid_org_before_database_write():
    from app.routers.accounting import create_fixed_asset

    db = FakeDB()
    with pytest.raises(HTTPException) as exc:
        create_fixed_asset(payload=_payload(), org_id="bad-org", db=db, _user=str(uuid4()))
    assert exc.value.status_code == 400
    assert db.added == []
    assert db.committed is False
