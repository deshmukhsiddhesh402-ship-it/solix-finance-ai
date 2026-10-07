"""
Module: AI Finance Copilot — the deterministic logic behind natural-language
queries. Claude decides WHICH function to call and with what parameters
(via tool use in the copilot router); this file is what actually computes
the numbers, so answers are grounded in real arithmetic rather than the
model inventing figures.
"""
from collections import defaultdict
from datetime import date
import math


MAX_COPILOT_ENTRIES = 100_000
MAX_COPILOT_MONTHS_AHEAD = 24


def _validate_entries(entries: list[dict]) -> None:
    if not isinstance(entries, list) or len(entries) > MAX_COPILOT_ENTRIES:
        raise ValueError("Entry set exceeds the supported Copilot limit.")


def _finite_number(value, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number.")
    return float(value)


# ---------------------------------------------------------------------------
# "Show me expenses above ₹X"
# ---------------------------------------------------------------------------
def filter_transactions(
    entries: list[dict], min_amount: float = 0, account_type: str | None = "expense",
    start_date: date | None = None, end_date: date | None = None,
) -> list[dict]:
    """Filter journal lines by amount threshold, account type, and date range.
    Amount compared is debit for expense/asset, credit for income/liability
    (i.e. the "natural" side of that account type).
    """
    _validate_entries(entries)
    min_amount = _finite_number(min_amount, "min_amount")
    if min_amount < 0:
        raise ValueError("min_amount cannot be negative.")
    if account_type is not None and account_type not in {"expense", "income", "asset", "liability", "equity"}:
        raise ValueError("Invalid account_type.")
    results = []
    for e in entries:
        if account_type and e["account_type"] != account_type:
            continue
        if start_date and e["date"] < start_date:
            continue
        if end_date and e["date"] > end_date:
            continue
        amount = e["debit"] if e["account_type"] in ("expense", "asset") else e["credit"]
        if amount >= min_amount:
            results.append({**e, "amount": amount})
    results.sort(key=lambda r: r["amount"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# "Why did profit decrease this month?"
# ---------------------------------------------------------------------------
def compare_periods(entries: list[dict], period_a_prefix: str, period_b_prefix: str) -> dict:
    """Compare two periods (e.g. '2026-06' vs '2026-07') and identify which
    accounts drove the change in revenue, expenses, and net profit.
    period_a is treated as the earlier/baseline period, period_b as current.
    """
    _validate_entries(entries)
    for prefix in (period_a_prefix, period_b_prefix):
        if not isinstance(prefix, str) or len(prefix) != 7 or prefix[4] != "-":
            raise ValueError("Periods must use YYYY-MM format.")
    def _period_totals(prefix: str) -> dict:
        by_account = defaultdict(lambda: {"type": None, "net": 0.0})
        for e in entries:
            key = e["date"].strftime("%Y-%m") if hasattr(e["date"], "strftime") else str(e["date"])[:7]
            if key != prefix:
                continue
            acc = by_account[e["account_name"]]
            acc["type"] = e["account_type"]
            if e["account_type"] == "income":
                acc["net"] += e["credit"] - e["debit"]
            elif e["account_type"] == "expense":
                acc["net"] += e["debit"] - e["credit"]
        revenue = sum(v["net"] for v in by_account.values() if v["type"] == "income")
        expenses = sum(v["net"] for v in by_account.values() if v["type"] == "expense")
        return {"by_account": dict(by_account), "revenue": revenue, "expenses": expenses, "profit": revenue - expenses}

    a = _period_totals(period_a_prefix)
    b = _period_totals(period_b_prefix)

    # Find which individual accounts changed the most between periods (the "drivers").
    all_accounts = set(a["by_account"]) | set(b["by_account"])
    drivers = []
    for acc in all_accounts:
        val_a = a["by_account"].get(acc, {"net": 0.0})["net"]
        val_b = b["by_account"].get(acc, {"net": 0.0})["net"]
        change = val_b - val_a
        if abs(change) > 0.01:
            acc_type = (a["by_account"].get(acc) or b["by_account"].get(acc))["type"]
            drivers.append({"account": acc, "type": acc_type, "period_a": round(val_a, 2), "period_b": round(val_b, 2), "change": round(change, 2)})
    drivers.sort(key=lambda d: abs(d["change"]), reverse=True)

    return {
        "period_a": {"label": period_a_prefix, "revenue": round(a["revenue"], 2), "expenses": round(a["expenses"], 2), "profit": round(a["profit"], 2)},
        "period_b": {"label": period_b_prefix, "revenue": round(b["revenue"], 2), "expenses": round(b["expenses"], 2), "profit": round(b["profit"], 2)},
        "profit_change": round(b["profit"] - a["profit"], 2),
        "top_drivers": drivers[:5],
    }


# ---------------------------------------------------------------------------
# "Predict next month's cash flow"
# ---------------------------------------------------------------------------
def predict_cash_flow(monthly_net: list[float], months_ahead: int = 1) -> dict:
    """Simple linear-regression trend projection over historical monthly net
    cash flow. This is a plain statistical extrapolation, NOT a machine-
    learning model — it assumes the recent trend continues linearly, which
    is a reasonable rough estimate for a few months out but will miss
    seasonality, one-off events, or trend changes. Say so to the user
    rather than presenting it as more certain than it is.
    """
    if not isinstance(monthly_net, list) or len(monthly_net) > 120:
        raise ValueError("Historical cash-flow series exceeds the supported limit.")
    if isinstance(months_ahead, bool) or not isinstance(months_ahead, int) or not 1 <= months_ahead <= MAX_COPILOT_MONTHS_AHEAD:
        raise ValueError("months_ahead must be between 1 and 24.")
    monthly_net = [_finite_number(v, "monthly_net") for v in monthly_net]
    n = len(monthly_net)
    if n < 2:
        raise ValueError("Need at least 2 months of history to project a trend.")

    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(monthly_net) / n
    numerator = sum((xs[i] - mean_x) * (monthly_net[i] - mean_y) for i in range(n))
    denominator = sum((xs[i] - mean_x) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0.0
    intercept = mean_y - slope * mean_x

    predictions = [round(intercept + slope * (n - 1 + m), 2) for m in range(1, months_ahead + 1)]

    return {
        "historical_months": n,
        "trend_slope_per_month": round(slope, 2),
        "predictions": predictions,
        "method": "linear trend regression (simple statistical extrapolation, not ML)",
        "caveat": "Assumes the recent trend continues; does not account for seasonality or one-off events.",
    }


# ---------------------------------------------------------------------------
# "Generate GST summary"
# ---------------------------------------------------------------------------
def gst_summary_from_entries(entries: list[dict]) -> dict:
    """Sum GST-related liability accounts from posted journal data —
    complements the standalone GST calculator (tax_engine.py) which works
    from manually-entered invoice values instead of posted books.
    """
    _validate_entries(entries)
    gst_accounts = defaultdict(float)
    for e in entries:
        if e["account_type"] == "liability" and "gst" in (e["account_name"] or "").lower():
            gst_accounts[e["account_name"]] += e["credit"] - e["debit"]

    total = sum(gst_accounts.values())
    return {
        "by_account": {k: round(v, 2) for k, v in gst_accounts.items()},
        "total_gst_liability": round(total, 2),
    }
