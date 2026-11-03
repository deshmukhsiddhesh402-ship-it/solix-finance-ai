"""Regression tests for controlled dashboard aggregate API errors."""

import pytest
from fastapi import HTTPException

from app.routers import dashboard


@pytest.mark.parametrize(
    "calculator",
    ["compute_dashboard_kpis", "monthly_trend", "expense_breakdown"],
)
def test_dashboard_calculation_maps_invalid_aggregates_to_422(monkeypatch, calculator):
    def reject(_entries):
        raise ValueError("Aggregate exceeds the supported numeric range.")

    monkeypatch.setattr(dashboard, calculator, reject)

    with pytest.raises(HTTPException) as exc:
        dashboard._calculate_dashboard([], include_breakdown=True)

    assert exc.value.status_code == 422
    assert exc.value.detail == "Aggregate exceeds the supported numeric range."


def test_dashboard_calculation_preserves_successful_results(monkeypatch):
    monkeypatch.setattr(dashboard, "compute_dashboard_kpis", lambda _entries: {"revenue": 10.0})
    monkeypatch.setattr(dashboard, "monthly_trend", lambda _entries: [{"month": "2026-11"}])
    monkeypatch.setattr(dashboard, "expense_breakdown", lambda _entries: [{"name": "Rent", "value": 5.0}])

    assert dashboard._calculate_dashboard([]) == (
        {"revenue": 10.0},
        [{"month": "2026-11"}],
        [{"name": "Rent", "value": 5.0}],
    )


def test_dashboard_pdf_calculation_skips_unused_expense_breakdown(monkeypatch):
    monkeypatch.setattr(dashboard, "compute_dashboard_kpis", lambda _entries: {"revenue": 10.0})
    monkeypatch.setattr(dashboard, "monthly_trend", lambda _entries: [{"month": "2026-11"}])

    def unexpected(_entries):
        raise AssertionError("PDF export must not calculate the unused expense breakdown.")

    monkeypatch.setattr(dashboard, "expense_breakdown", unexpected)

    assert dashboard._calculate_dashboard([], include_breakdown=False) == (
        {"revenue": 10.0},
        [{"month": "2026-11"}],
        None,
    )
