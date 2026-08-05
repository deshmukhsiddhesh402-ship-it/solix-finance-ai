"""
Module 6: Financial Analysis engine — NPV, IRR, CAGR, Break-even, DCF
Valuation, and Scenario Analysis. Pure Python (no numpy/scipy dependency)
so it's lightweight and easy to unit test.
"""
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# NPV
# ---------------------------------------------------------------------------
def npv(rate_pct: float, cash_flows: list[float]) -> float:
    """cash_flows[0] is the initial outlay (typically negative), followed by
    period 1, 2, 3... cash inflows/outflows."""
    r = rate_pct / 100
    total = sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows))
    return round(total, 2)


# ---------------------------------------------------------------------------
# IRR — bisection method (robust, no external deps)
# ---------------------------------------------------------------------------
def irr(cash_flows: list[float], low: float = -99.0, high: float = 1000.0, tol: float = 1e-6, max_iter: int = 200) -> float | None:
    """Find the discount rate (%) at which NPV == 0, via bisection.
    Returns None if no sign change is found in the search range (no real IRR).
    """
    def npv_at(rate_pct: float) -> float:
        r = rate_pct / 100
        return sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows))

    f_low, f_high = npv_at(low), npv_at(high)
    if f_low * f_high > 0:
        return None  # no sign change => bisection can't bracket a root

    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = npv_at(mid)
        if abs(f_mid) < tol:
            return round(mid, 4)
        if f_low * f_mid < 0:
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
