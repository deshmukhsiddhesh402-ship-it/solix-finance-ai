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


def _matches_any(name: str, keywords: list[str]) -> bool:
    lower = (name or "").lower()
    return any(k in lower for k in keywords)


def compute_dashboard_kpis(entries: list[dict]) -> dict:
    """entries: list of {date: date, account_name: str, account_type: str, debit: float, credit: float}"""
    revenue = sum(e["credit"] - e["debit"] for e in entries if e["account_type"] == "income")
    expenses = sum(e["debit"] - e["credit"] for e in entries if e["account_type"] == "expense")
    net_profit = revenue - expenses

    cash_position = sum(
        e["debit"] - e["credit"] for e in entries
        if e["account_type"] == "asset" and _matches_any(e["account_name"], ["cash", "bank"])
    )
    receivables = sum(
        e["debit"] - e["credit"] for e in entries
        if e["account_type"] == "asset" and _matches_any(e["account_name"], ["receivable", "debtor"])
    )

    # Classify each liability into exactly one bucket (gst / tds / generic payables) so an
    # account like "GST Output Payable" isn't double-counted into both GST liability AND payables.
    gst_liability = 0.0
    tds_payable = 0.0
    payables = 0.0
    for e in entries:
        if e["account_type"] != "liability":
            continue
        name = (e["account_name"] or "").lower()
        net = e["credit"] - e["debit"]
        if "gst" in name:
            gst_liability += net
        elif "tds" in name:
            tds_payable += net
        elif _matches_any(name, ["payable", "creditor"]):
            payables += net

    total_assets = sum(e["debit"] - e["credit"] for e in entries if e["account_type"] == "asset")
    total_liabilities = sum(e["credit"] - e["debit"] for e in entries if e["account_type"] == "liability")
    working_capital = total_assets - total_liabilities  # simplification: not split into current vs non-current

    profit_margin_pct = round((net_profit / revenue) * 100, 2) if revenue else None

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
    """Group revenue/expenses by calendar month (YYYY-MM), sorted chronologically."""
    buckets = defaultdict(lambda: {"revenue": 0.0, "expenses": 0.0})
    for e in entries:
        key = e["date"].strftime("%Y-%m") if isinstance(e["date"], date) else str(e["date"])[:7]
        if e["account_type"] == "income":
            buckets[key]["revenue"] += e["credit"] - e["debit"]
        elif e["account_type"] == "expense":
            buckets[key]["expenses"] += e["debit"] - e["credit"]

    return [
        {"month": k, "revenue": round(v["revenue"], 2), "expenses": round(v["expenses"], 2)}
        for k, v in sorted(buckets.items())
    ]


def expense_breakdown(entries: list[dict]) -> list[dict]:
    """Total expense per account name — feeds the pie chart."""
    totals = defaultdict(float)
    for e in entries:
        if e["account_type"] == "expense":
            totals[e["account_name"]] += e["debit"] - e["credit"]
    return sorted(
        [{"name": k, "value": round(v, 2)} for k, v in totals.items() if v > 0],
        key=lambda x: x["value"], reverse=True,
    )
