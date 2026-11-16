"""Regression tests for non-posting Decimal fixed asset depreciation previews."""

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

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def first(self):
        return self.item


class FakeDB:
    def __init__(self, item):
        self.query_result = FakeQuery(item)
        self.queries = []

    def query(self, model):
        self.queries.append(model)
        return self.query_result


def _asset(method="straight_line", cost="1000.00", salvage="100.00", years=3):
    return SimpleNamespace(
        id=uuid4(), org_id=uuid4(), asset_name="Machine",
        purchase_date=date(2026, 1, 1), cost=Decimal(cost),
        salvage_value=Decimal(salvage), useful_life_years=years,
        depreciation_method=method, is_active=True,
    )


def _payload(**overrides):
    from app.routers.accounting import FixedAssetDepreciationPreviewRequest

    return FixedAssetDepreciationPreviewRequest(**overrides)


def test_straight_line_preview_uses_decimal_and_final_period_reconciliation():
    from app.routers.accounting import preview_fixed_asset_depreciation

    asset = _asset()
    result = preview_fixed_asset_depreciation(
        asset_id=str(asset.id), payload=_payload(), org_id=str(asset.org_id),
        db=FakeDB(asset), _user=str(uuid4()),
    )
    assert [row["depreciation"] for row in result["schedule"]] == ["300.00", "300.00", "300.00"]
    assert result["schedule"][-1]["closing_value"] == "100.00"
    assert result["wdv_rate_pct"] is None
    assert "no depreciation journal is posted" in result["disclaimer"]


def test_wdv_preview_requires_explicit_user_supplied_rate_and_respects_salvage_floor():
    from app.routers.accounting import preview_fixed_asset_depreciation

    asset = _asset(method="wdv")
    with pytest.raises(HTTPException) as missing:
        preview_fixed_asset_depreciation(
            asset_id=str(asset.id), payload=_payload(), org_id=str(asset.org_id),
            db=FakeDB(asset), _user=str(uuid4()),
        )
    assert missing.value.status_code == 422
    result = preview_fixed_asset_depreciation(
        asset_id=str(asset.id), payload=_payload(wdv_rate_pct=Decimal("50.00")),
        org_id=str(asset.org_id), db=FakeDB(asset), _user=str(uuid4()),
    )
    assert [row["depreciation"] for row in result["schedule"]] == ["500.00", "250.00", "150.00"]
    assert result["schedule"][-1]["closing_value"] == "100.00"
    assert result["wdv_rate_pct"] == "50.00"


def test_straight_line_preview_rejects_a_wdv_rate():
    from app.routers.accounting import preview_fixed_asset_depreciation

    asset = _asset()
    with pytest.raises(HTTPException) as exc:
        preview_fixed_asset_depreciation(
            asset_id=str(asset.id), payload=_payload(wdv_rate_pct=Decimal("15")),
            org_id=str(asset.org_id), db=FakeDB(asset), _user=str(uuid4()),
        )
    assert exc.value.status_code == 422


def test_fixed_asset_depreciation_preview_does_not_disclose_foreign_tenant():
    from app.routers.accounting import preview_fixed_asset_depreciation

    db = FakeDB(None)
    with pytest.raises(HTTPException) as exc:
        preview_fixed_asset_depreciation(
            asset_id=str(uuid4()), payload=_payload(), org_id=str(uuid4()),
            db=db, _user=str(uuid4()),
        )
    assert exc.value.status_code == 404


@pytest.mark.parametrize("rate", [True, Decimal("0"), Decimal("100.01")])
def test_fixed_asset_depreciation_preview_rejects_invalid_wdv_rates(rate):
    with pytest.raises(ValidationError):
        _payload(wdv_rate_pct=rate)


def test_fixed_asset_depreciation_preview_requires_fixed_asset_view_permission():
    from app.routers.accounting import router

    route = next(
        route for route in router.routes
        if getattr(route, "path", None) == "/fixed-assets/{asset_id}/depreciation-preview"
    )
    dependency = next(
        dependency.call for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    assert (closure["resource"], closure["action"]) == ("fixed_assets", "view")
