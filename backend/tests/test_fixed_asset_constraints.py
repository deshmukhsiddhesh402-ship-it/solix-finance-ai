"""Fixed asset ORM and migration invariants."""

def test_fixed_asset_model_requires_tenant_and_financial_constraints():
    from app.models.accounting import FixedAsset

    table = FixedAsset.__table__
    assert table.c.org_id.nullable is False
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if getattr(constraint, "name", None)
    }
    for name in [
        "ck_fixed_asset_cost_nonnegative",
        "ck_fixed_asset_salvage_nonnegative",
        "ck_fixed_asset_salvage_not_above_cost",
        "ck_fixed_asset_useful_life_positive",
        "ck_fixed_asset_depreciation_method",
        "ck_fixed_asset_name_nonblank",
    ]:
        assert name in constraints


def test_fixed_asset_migration_fails_closed_and_scopes_constraint_names():
    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "migrations"
        / "012_fixed_asset_integrity.sql"
    ).read_text(encoding="utf-8")
    assert "org_id IS NULL" in migration
    assert "salvage_value > cost" in migration
    assert "useful_life_years <= 0" in migration
    assert "RAISE EXCEPTION" in migration
    assert migration.count("conrelid = 'fixed_assets'::regclass") == 6


def test_fixed_asset_register_uses_fixed_asset_read_permission():
    from app.routers.accounting import router

    route = next(route for route in router.routes if getattr(route, "path", None) == "/fixed-assets" and "GET" in route.methods)
    dependency = next(
        dependency.call for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    assert (closure["resource"], closure["action"]) == ("fixed_assets", "view")


def test_fixed_asset_create_requires_fixed_asset_create_permission():
    from app.routers.accounting import router

    route = next(route for route in router.routes if getattr(route, "path", None) == "/fixed-assets" and "POST" in route.methods)
    dependency = next(
        dependency.call for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    assert (closure["resource"], closure["action"]) == ("fixed_assets", "create")
