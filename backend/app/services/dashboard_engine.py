"""
Module: Live Financial Dashboard — aggregation engine.

Pure functions operating on a flat list of journal-line dicts (each with
date, account_name, account_type, debit, credit) — deliberately DB-agnostic
so it's fully unit-testable without a live Postgres connection. The
dashboard router (dashboard.py) converts real DB rows into this shape.

CLASSIFICATION NOTE: receivables/payables/GST/TDS/cash are identified by
keyword-matching the account name (e.g. "contains 'receivable'"). This is a
reasonable default for a chart of accounts using conventional naming, but a
production system should tag accounts with an explicit `sub_type` field in
`chart_of_accounts` instead of relying on name matching — flagged here
rather than silently assumed reliable.
"""
from collections import defaultdict
from datetime import date
import math


def _matches_any(name: str, keywords: list[str]) -> bool:
    lower = (name or "").lower()
    return any(k in lower for k in keywords)


def _safe_sum(values, label: str) -> float:
    try:
        total = math.fsum(values)
    except OverflowError as exc:
        raise ValueError(f"{label} exceeds the supported numeric range.") from exc
    if not math.isfinite(total):
        raise ValueError(f"{label} exceeds the supported numeric range.")
    return total


def _validate_entry_amounts(entries: list[dict]) -> None:
    if not isinstance(entries, list):
        raise ValueError("entries must be a list.")
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"entries[{index}] must be an object.")
        for field in ("debit", "credit"):
            if field not in entry:
                raise ValueError(f"entries[{index}].{field} is required.")
            value = entry[field]
            try:
                finite = math.isfinite(value)
            except (OverflowError, TypeError):
                finite = False
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not finite:
                raise ValueError(f"entries[{index}].{field} must be a finite number.")


def compute_dashboard_kpis(entries: list[dict]) -> dict:
    """entries: list of {date: date, account_name: str, account_type: str, debit: float, credit: float}"""
    _validate_entry_amounts(entries)
    revenue = _safe_sum((e["credit"] - e["debit"] for e in entries if e["account_type"] == "income"), "Revenue total")
    expenses = _safe_sum((e["debit"] - e["credit"] for e in entries if e["account_type"] == "expense"), "Expense total")
    net_profit = revenue - expenses
    if not math.isfinite(net_profit):
        raise ValueError("Net profit exceeds the supported numeric range.")

    cash_position = _safe_sum((
        e["debit"] - e["credit"] for e in entries
        if e["account_type"] == "asset" and _matches_any(e["account_name"], ["cash", "bank"])
    ), "Cash position")
    receivables = _safe_sum((
        e["debit"] - e["credit"] for e in entries
        if e["account_type"] == "asset" and _matches_any(e["account_name"], ["receivable", "debtor"])
    ), "Receivables")

    # Classify each liability into exactly one bucket (gst / tds / generic payables).
    gst_liability = _safe_sum((e["credit"] - e["debit"] for e in entries if e["account_type"] == "liability" and "gst" in (e["account_name"] or "").lower()), "GST liability")
    tds_payable = _safe_sum((e["credit"] - e["debit"] for e in entries if e["account_type"] == "liability" and "tds" in (e["account_name"] or "").lower() and "gst" not in (e["account_name"] or "").lower()), "TDS payable")
    payables = _safe_sum((e["credit"] - e["debit"] for e in entries if e["account_type"] == "liability" and "gst" not in (e["account_name"] or "").lower() and "tds" not in (e["account_name"] or "").lower() and _matches_any(e["account_name"], ["payable", "creditor"])), "Payables")

    total_assets = _safe_sum((e["debit"] - e["credit"] for e in entries if e["account_type"] == "asset"), "Asset total")
    total_liabilities = _safe_sum((e["credit"] - e["debit"] for e in entries if e["account_type"] == "liability"), "Liability total")
    working_capital = total_assets - total_liabilities
    if not math.isfinite(working_capital):
        raise ValueError("Working capital exceeds the supported numeric range.")

    if revenue:
        margin = (net_profit / revenue) * 100
        if not math.isfinite(margin):
            raise ValueError("Profit margin exceeds the supported numeric range.")
        profit_margin_pct = round(margin, 2)
    else:
        profit_margin_pct = None

    return {
        "revenue": round(revenue, 2),
        "expenses": round(expenses, 2),
        "net_profit": round(net_profit, 2),
        "cash_position": round(cash_position, 2),
        "receivables": round(receivables, 2),
        "payables": round(payables, 2),
        "gst_liability": round(gst_liability, 2),
        "tds_payable": round(tds_payable, 2),
        "profit_margin_pct": profit_margin_pct,
        "working_capital": round(working_capital, 2),
    }


def monthly_trend(entries: list[dict]) -> list[dict]:
    """Group revenue/expenses by calendar month (YYYY-MM), with checked totals."""
    _validate_entry_amounts(entries)
    buckets = defaultdict(lambda: {"revenue": [], "expenses": []})
    for entry in entries:
        key = entry["date"].strftime("%Y-%m") if isinstance(entry["date"], date) else str(entry["date"])[:7]
        if entry["account_type"] == "income":
            buckets[key]["revenue"].append(entry["credit"] - entry["debit"])
        elif entry["account_type"] == "expense":
            buckets[key]["expenses"].append(entry["debit"] - entry["credit"])

    result = []
    for month, values in sorted(buckets.items()):
        revenue = _safe_sum(values["revenue"], f"{month} revenue")
        expenses = _safe_sum(values["expenses"], f"{month} expenses")
        result.append({"month": month, "revenue": round(revenue, 2), "expenses": round(expenses, 2)})
    return result


def expense_breakdown(entries: list[dict]) -> list[dict]:
    """Total expense per account name — feeds the pie chart."""
    _validate_entry_amounts(entries)
    amounts = defaultdict(list)
    for entry in entries:
        if entry["account_type"] == "expense":
            amounts[entry["account_name"]].append(entry["debit"] - entry["credit"])

    totals = [
        {"name": name, "value": round(_safe_sum(values, f"{name} expense total"), 2)}
        for name, values in amounts.items()
    ]
    return sorted((item for item in totals if item["value"] > 0), key=lambda item: item["value"], reverse=True)
