"""Guard the intended access boundary of the accounting router.

Persisted ledger writes require tenant-scoped RBAC. Pure calculators accept only
request data and intentionally remain independent of tenant/database state.
"""

from fastapi.routing import APIRoute

from app.core.db import get_db
from app.routers.accounting import router


EXPECTED_ACCESS_POLICY = {
    ("POST", "/journal-entries"): "tenant_scoped",
    ("POST", "/trial-balance"): "stateless",
    ("POST", "/profit-and-loss"): "stateless",
    ("POST", "/balance-sheet"): "stateless",
    ("POST", "/ratios"): "stateless",
    ("POST", "/depreciation/straight-line"): "stateless",
    ("POST", "/depreciation/wdv"): "stateless",
    ("POST", "/inventory/valuation"): "stateless",
}


def _dependency_calls(dependant):
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from _dependency_calls(dependency)


def test_every_accounting_route_has_an_explicit_access_policy():
    routes = [route for route in router.routes if isinstance(route, APIRoute)]
    actual = {
        (method, route.path)
        for route in routes
        for method in route.methods
    }

    assert actual == set(EXPECTED_ACCESS_POLICY)

    for route in routes:
        calls = tuple(_dependency_calls(route.dependant))
        for method in route.methods:
            policy = EXPECTED_ACCESS_POLICY[(method, route.path)]
            has_permission_dependency = any(
                getattr(call, "__name__", None) == "_dependency"
                and getattr(call, "__module__", None) == "app.routers.enterprise"
                for call in calls
            )

            if policy == "tenant_scoped":
                assert get_db in calls
                assert has_permission_dependency
            else:
                assert get_db not in calls
                assert not has_permission_dependency
