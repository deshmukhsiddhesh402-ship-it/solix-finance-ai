"""
Module 6: Financial Analysis engine — NPV, IRR, CAGR, Break-even, DCF
Valuation, and Scenario Analysis. Pure Python (no numpy/scipy dependency)
so it's lightweight and easy to unit test.
"""
from dataclasses import dataclass
import math


def _require_finite_number(value: float, label: str) -> None:
    """Reject booleans, non-numeric values, NaN, and infinities at engine boundaries."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")


def _require_cash_flows(cash_flows: list[float], label: str = "cash_flows") -> None:
    if not isinstance(cash_flows, list) or not cash_flows:
        raise ValueError(f"{label} must be a non-empty list.")
    for index, value in enumerate(cash_flows):
        _require_finite_number(value, f"{label}[{index}]")


# ---------------------------------------------------------------------------
# NPV
# ---------------------------------------------------------------------------
def npv(rate_pct: float, cash_flows: list[float]) -> float:
    """cash_flows[0] is the initial outlay (typically negative), followed by
    period 1, 2, 3... cash inflows/outflows."""
    _require_finite_number(rate_pct, "rate_pct")
    _require_cash_flows(cash_flows)
    if rate_pct <= -100:
        raise ValueError("rate_pct must be greater than -100.")
    r = rate_pct / 100
    total = sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows))
    if not math.isfinite(total):
        raise ValueError("NPV result is not finite for the supplied inputs.")
    return round(total, 2)


# ---------------------------------------------------------------------------
# IRR — bisection method (robust, no external deps)
# ---------------------------------------------------------------------------
def irr(cash_flows: list[float], low: float = -99.0, high: float = 1000.0, tol: float = 1e-6, max_iter: int = 200) -> float | None:
    """Find the discount rate (%) at which NPV == 0, via bisection.
    Returns None if no sign change is found in the search range (no real IRR).
    """
    _require_cash_flows(cash_flows)
    for value, label in ((low, "low"), (high, "high"), (tol, "tol")):
        _require_finite_number(value, label)
    if low <= -100 or high <= -100 or low >= high:
        raise ValueError("IRR bounds must satisfy -100 < low < high.")
    if tol <= 0:
        raise ValueError("tol must be positive.")
    if isinstance(max_iter, bool) or not isinstance(max_iter, int) or max_iter < 1:
        raise ValueError("max_iter must be a positive integer.")

    def npv_at(rate_pct: float) -> float:
        r = rate_pct / 100
        return sum(cf / ((1 + r) ** t) for t, cf in enumerate(cash_flows))

    f_low, f_high = npv_at(low), npv_at(high)
    if not math.isfinite(f_low) or not math.isfinite(f_high):
        raise ValueError("IRR is not finite for the supplied inputs and bounds.")
    if f_low * f_high > 0:
        return None  # no sign change => bisection can't bracket a root

    for _ in range(max_iter):
        mid = (low + high) / 2
        f_mid = npv_at(mid)
        if not math.isfinite(f_mid):
            raise ValueError("IRR is not finite for the supplied inputs and bounds.")
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
    for value, label in ((beginning_value, "beginning_value"), (ending_value, "ending_value"), (years, "years")):
        _require_finite_number(value, label)
    if beginning_value <= 0 or ending_value <= 0 or years <= 0:
        raise ValueError("beginning_value, ending_value, and years must be positive")
    rate = (ending_value / beginning_value) ** (1 / years) - 1
    if not math.isfinite(rate):
        raise ValueError("CAGR result is not finite for the supplied inputs.")
    return round(rate * 100, 2)


# ---------------------------------------------------------------------------
# Break-even Analysis
# ---------------------------------------------------------------------------
def break_even(fixed_costs: float, price_per_unit: float, variable_cost_per_unit: float) -> dict:
    for value, label in (
        (fixed_costs, "fixed_costs"),
        (price_per_unit, "price_per_unit"),
        (variable_cost_per_unit, "variable_cost_per_unit"),
    ):
        _require_finite_number(value, label)
    if fixed_costs < 0 or variable_cost_per_unit < 0 or price_per_unit <= 0:
        raise ValueError("fixed_costs and variable_cost_per_unit must be non-negative, and price_per_unit must be positive.")
    contribution_margin = price_per_unit - variable_cost_per_unit
    if contribution_margin <= 0:
        raise ValueError("Price per unit must exceed variable cost per unit")
    break_even_units = fixed_costs / contribution_margin
    break_even_revenue = break_even_units * price_per_unit
    if not math.isfinite(break_even_units) or not math.isfinite(break_even_revenue):
        raise ValueError("Break-even result is not finite for the supplied inputs.")
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
    _require_cash_flows(projected_cash_flows, "projected_cash_flows")
    _require_finite_number(discount_rate_pct, "discount_rate_pct")
    _require_finite_number(terminal_growth_rate_pct, "terminal_growth_rate_pct")
    if discount_rate_pct <= -100 or terminal_growth_rate_pct <= -100:
        raise ValueError("Discount and terminal growth rates must be greater than -100.")
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
    values = (sum_pv_cash_flows, terminal_value, pv_terminal_value, enterprise_value)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("DCF result is not finite for the supplied inputs.")
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
    if not isinstance(scenarios, list):
        raise ValueError("scenarios must be a list of Scenario objects.")

    rows = []
    raw_profits = []
    weighted_profit = 0.0
    total_prob = 0.0
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, Scenario):
            raise ValueError(f"scenarios[{index}] must be a Scenario object.")
        if not isinstance(scenario.name, str) or not scenario.name.strip():
            raise ValueError(f"scenarios[{index}].name must be a non-empty string.")
        for value, label in (
            (scenario.revenue, f"scenarios[{index}].revenue"),
            (scenario.cost, f"scenarios[{index}].cost"),
            (scenario.probability_pct, f"scenarios[{index}].probability_pct"),
        ):
            _require_finite_number(value, label)
        if scenario.probability_pct < 0 or scenario.probability_pct > 100:
            raise ValueError(f"scenarios[{index}].probability_pct must be between 0 and 100.")

        total_prob += scenario.probability_pct
        profit = scenario.revenue - scenario.cost
        if not math.isfinite(profit):
            raise ValueError(f"scenarios[{index}] profit is not finite.")
        raw_profits.append(profit)
        rows.append({
            "name": scenario.name, "revenue": scenario.revenue, "cost": scenario.cost,
            "profit": round(profit, 2), "probability_pct": scenario.probability_pct,
        })

    if not math.isfinite(total_prob):
        raise ValueError("Total scenario probability must be finite.")
    if total_prob > 0:
        weighted_profit = sum(
            profit * (row["probability_pct"] / total_prob)
            for profit, row in zip(raw_profits, rows)
        )
        if not math.isfinite(weighted_profit):
            raise ValueError("Expected scenario profit is not finite.")

    return {
        "scenarios": rows,
        "expected_profit": round(weighted_profit, 2) if total_prob > 0 else None,
        "best_case": max(rows, key=lambda r: r["profit"])["name"] if rows else None,
        "worst_case": min(rows, key=lambda r: r["profit"])["name"] if rows else None,
    }
