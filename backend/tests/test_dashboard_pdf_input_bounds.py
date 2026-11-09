"""Regression tests for dashboard PDF query input bounds."""

from app.routers import dashboard


def test_dashboard_pdf_organization_name_has_query_length_bound():
    route = next(route for route in dashboard.router.routes if route.path == "/export/pdf")
    parameter = next(item for item in route.dependant.query_params if item.name == "org_name")

    assert parameter.field_info.max_length == 120
