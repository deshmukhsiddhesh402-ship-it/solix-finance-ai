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


def test_dashboard_kpis_rejects_integer_amount_outside_float_range():
    with pytest.raises(ValueError, match="finite number"):
        compute_dashboard_kpis([_entry(credit=10**1000)])


def test_dashboard_kpis_rejects_aggregate_overflow():
    entries = [
        _entry(credit=1e308),
        _entry(account_name="Other Revenue", credit=1e308),
    ]
    with pytest.raises(ValueError, match="supported numeric range"):
        compute_dashboard_kpis(entries)


def test_monthly_trend_preserves_finite_monthly_totals():
    from app.services.dashboard_engine import monthly_trend

    entries = [
        _entry(date="2026-11-01", credit=125.50),
        _entry(date="2026-11-15", credit=74.50),
        _entry(account_type="expense", account_name="Rent", date="2026-11-20", debit=50.0),
    ]
    assert monthly_trend(entries) == [
        {"month": "2026-11", "revenue": 200.0, "expenses": 50.0}
    ]


def test_monthly_trend_rejects_non_finite_amounts():
    from app.services.dashboard_engine import monthly_trend

    with pytest.raises(ValueError, match="finite number"):
        monthly_trend([_entry(credit=float("nan"))])


def test_monthly_trend_rejects_monthly_aggregate_overflow():
    from app.services.dashboard_engine import monthly_trend

    entries = [
        _entry(credit=1e308),
        _entry(date="2026-11-02", credit=1e308),
    ]
    with pytest.raises(ValueError, match="supported numeric range"):
        monthly_trend(entries)


def test_expense_breakdown_preserves_finite_account_totals():
    from app.services.dashboard_engine import expense_breakdown

    entries = [
        _entry(account_type="expense", account_name="Rent", debit=100.0),
        _entry(account_type="expense", account_name="Rent", debit=50.0),
        _entry(account_type="expense", account_name="Utilities", debit=25.0),
    ]
    assert expense_breakdown(entries) == [
        {"name": "Rent", "value": 150.0},
        {"name": "Utilities", "value": 25.0},
    ]


def test_expense_breakdown_rejects_account_aggregate_overflow():
    from app.services.dashboard_engine import expense_breakdown

    entries = [
        _entry(account_type="expense", account_name="Rent", debit=1e308),
        _entry(account_type="expense", account_name="Rent", debit=1e308),
    ]
    with pytest.raises(ValueError, match="supported numeric range"):
        expense_breakdown(entries)
