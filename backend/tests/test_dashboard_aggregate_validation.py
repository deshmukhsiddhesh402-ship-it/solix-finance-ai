"""Regression tests for dashboard financial aggregate boundaries."""
import pytest

from app.services.dashboard_engine import compute_dashboard_kpis


def _entry(**overrides):
    values = {
        "date": "2026-11-01",
        "account_name": "Sales Revenue",
        "account_type": "income",
        "debit": 0.0,
        "credit": 100.0,
    }
    return {**values, **overrides}


def test_dashboard_kpis_preserves_normal_finite_values():
    result = compute_dashboard_kpis([_entry()])
    assert result["revenue"] == 100.0
    assert result["net_profit"] == 100.0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True])
def test_dashboard_kpis_rejects_non_finite_or_boolean_amounts(value):
    with pytest.raises(ValueError, match="finite number"):
        compute_dashboard_kpis([_entry(credit=value)])


def test_dashboard_kpis_rejects_aggregate_overflow():
    entries = [
        _entry(credit=1e308),
        _entry(account_name="Other Revenue", credit=1e308),
    ]
    with pytest.raises(ValueError, match="supported numeric range"):
        compute_dashboard_kpis(entries)
