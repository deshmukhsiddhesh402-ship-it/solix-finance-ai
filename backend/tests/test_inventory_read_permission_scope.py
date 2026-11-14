"""Ensure inventory read endpoints use inventory-specific RBAC permissions."""


def _permission_for_route(path: str):
    from app.routers.accounting import router

    route = next(route for route in router.routes if getattr(route, "path", None) == path)
    dependency = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "_dependency"
    )
    closure = dict(zip(
        dependency.__code__.co_freevars,
        (cell.cell_contents for cell in dependency.__closure__ or ()),
    ))
    return closure["resource"], closure["action"]


def test_inventory_item_register_requires_inventory_view_permission():
    assert _permission_for_route("/inventory/items") == ("inventory", "view")


def test_inventory_transaction_ledger_requires_inventory_view_permission():
    assert _permission_for_route("/inventory/items/{item_id}/transactions") == ("inventory", "view")
