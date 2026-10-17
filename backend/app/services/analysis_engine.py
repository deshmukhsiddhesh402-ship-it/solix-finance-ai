"""
Module 6: Financial Analysis engine — NPV, IRR, CAGR, Break-even, DCF
Valuation, and Scenario Analysis. Pure Python (no numpy/scipy dependency)
so it's lightweight and easy to unit test.
"""
from dataclasses import dataclass
import math


# ---------------------------------------------------------------------------
# NPV / IRR input validation
# ---------------------------------------------------------------------------
def _require_finite_number(value: object, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number.")
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    if not finite:
        raise ValueError(f"{label} must be a finite number.")


def _validated_cash_flows(cash_flows: object) -> list[float]:
    if not isinstance(cash_flows, list) or not cash_flows:
        raise ValueError("cash_flows must be a non-empty list.")
    for index, cash_flow in enumerate(cash_flows):
        _require_finite_number(cash_flow, f"cash_flows[{index}]")
    return cash_flows


def _npv_at_rate(rate_pct: float, cash_flows: list[float]) -> float:
    rate = rate_pct / 100
    try:
        total = sum(cf / ((1 + rate) ** period) for period, cf in enumerate(cash_flows))
    except (OverflowError, ZeroDivisionError) as exc:
        raise ValueError("NPV calculation exceeds the supported numeric range.") from exc
    _require_finite_number(total, "NPV result")
    return total


# ---------------------------------------------------------------------------
# NPV
# ---------------------------------------------------------------------------
def npv(rate_pct: float, cash_flows: list[float]) -> float:
    """cash_flows[0] is the initial outlay (typically negative), followed by
    period 1, 2, 3... cash inflows/outflows."""
    _require_finite_number(rate_pct, "rate_pct")
    if rate_pct <= -100:
        raise ValueError("rate_pct must be greater than -100%.")
    values = _validated_cash_flows(cash_flows)
    return round(_npv_at_rate(rate_pct, values), 2)


# ---------------------------------------------------------------------------
# IRR — bisection method (robust, no external deps)
# ---------------------------------------------------------------------------
def irr(cash_flows: list[float], low: float = -99.0, high: float = 1000.0, tol: float = 1e-6, max_iter: int = 200) -> float | None:
    """Find the discount rate (%) at which NPV == 0, via bisection.
    Returns None if no sign change is found in the search range (no real IRR).
    """
    values = _validated_cash_flows(cash_flows)
    _require_finite_number(low, "low")
    _require_finite_number(high, "high")
    _require_finite_number(tol, "tol")
    if low <= -100:
        raise ValueError("low must be greater than -100%.")
    if low >= high:
        raise ValueError("low must be less than high.")
    if tol <= 0:
        raise ValueError("tol must be greater than zero.")
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter <= 0:
        raise ValueError("max_iter must be a positive integer.")

    f_low = _npv_at_rate(low, values)
    f_high = _npv_at_rate(high, values)
    if f_low == 0:
        return round(low, 4)
    if f_high == 0:
        return round(high, 4)
    if (f_low > 0) == (f_high > 0):
        return None  # no sign change => bisection can't bracket a root

    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = _npv_at_rate(mid, values)
        if abs(f_mid) < tol:
            return round(mid, 4)
        if (f_low > 0) != (f_mid > 0):
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid
    return round((low + high) / 2, 4)


# ---------------------------------------------------------------------------
# CAGR
# ---------------------------------------------------------------------------
def cagr(beginning_value: float, ending_value: float, years: float) -> float:
    """Compound Annual Growth Rate, as a percentage."""
    if beginning_value <= 0 or years <= 0:
        raise ValueError("beginning_value and years must be positive")
    rate = (ending_value / beginning_value) ** (1 / years) - 1
    return round(rate * 100, 2)


# ---------------------------------------------------------------------------
# Break-even Analysis
# ---------------------------------------------------------------------------
def break_even(fixed_costs: float, price_per_unit: float, variable_cost_per_unit: float) -> dict:
    contribution_margin = price_per_unit - variable_cost_per_unit
    if contribution_margin <= 0:
        raise ValueError("Price per unit must exceed variable cost per unit")
    break_even_units = fixed_costs / contribution_margin
    break_even_revenue = break_even_units * price_per_unit
    return {
        "contribution_margin_per_unit": round(contribution_margin, 2),
        "contribution_margin_ratio_pct": round((contribution_margin / price_per_unit) * 100, 2),
        "break_even_units": round(break_even_units, 2),
        "break_even_revenue": round(break_even_revenue, 2),
    }


# ---------------------------------------------------------------------------
# DCF Valuation (with terminal value via Gordon Growth)
# ---------------------------------------------------------------------------
def dcf_valuation(
    projected_cash_flows: list[float],  # forecast period FCFs, period 1..n (no period-0 outlay here)
    discount_rate_pct: float,
    terminal_growth_rate_pct: float,
) -> dict:
    r = discount_rate_pct / 100
    g = terminal_growth_rate_pct / 100
    if r <= g:
        raise ValueError("Discount rate must exceed terminal growth rate")

    pv_cash_flows = [cf / ((1 + r) ** (t + 1)) for t, cf in enumerate(projected_cash_flows)]
    sum_pv_cash_flows = sum(pv_cash_flows)

    last_cf = projected_cash_flows[-1]
    terminal_value = (last_cf * (1 + g)) / (r - g)
    pv_terminal_value = terminal_value / ((1 + r) ** len(projected_cash_flows))

    enterprise_value = sum_pv_cash_flows + pv_terminal_value
    return {
        "pv_of_forecast_cash_flows": round(sum_pv_cash_flows, 2),
        "terminal_value": round(terminal_value, 2),
        "pv_of_terminal_value": round(pv_terminal_value, 2),
        "enterprise_value": round(enterprise_value, 2),
    }


# ---------------------------------------------------------------------------
# Scenario Analysis
# ---------------------------------------------------------------------------
@dataclass
class Scenario:
    name: str
    revenue: float
    cost: float
    probability_pct: float = 0.0


def scenario_analysis(scenarios: list[Scenario]) -> dict:
    rows = []
    weighted_profit = 0.0
    total_prob = sum(s.probability_pct for s in scenarios)
    for s in scenarios:
        profit = s.revenue - s.cost
        rows.append({
            "name": s.name, "revenue": s.revenue, "cost": s.cost,
            "profit": round(profit, 2), "probability_pct": s.probability_pct,
        })
        if total_prob > 0:
            weighted_profit += profit * (s.probability_pct / total_prob)

    return {
        "scenarios": rows,
        "expected_profit": round(weighted_profit, 2) if total_prob > 0 else None,
        "best_case": max(rows, key=lambda r: r["profit"])["name"] if rows else None,
        "worst_case": min(rows, key=lambda r: r["profit"])["name"] if rows else None,
    }
