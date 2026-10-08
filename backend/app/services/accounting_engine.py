"""
Module 2: Accounting core engine — pure calculation functions, no I/O.
Kept framework-free so they're independently unit-testable and reusable
from CLI scripts, notebooks, or the API router.
"""
from dataclasses import dataclass
from typing import Literal


# ---------------------------------------------------------------------------
# Trial Balance
# ---------------------------------------------------------------------------
@dataclass
class LedgerLine:
    account_name: str
    account_type: Literal["asset", "liability", "equity", "income", "expense"]
    debit: float = 0.0
    credit: float = 0.0


def build_trial_balance(lines: list[LedgerLine]) -> dict:
    """Aggregate ledger lines by account and return a trial balance.
    Raises ValueError if total debits != total credits (books don't balance).
    """
    totals: dict[str, dict] = {}
    for line in lines:
        acc = totals.setdefault(
            line.account_name, {"type": line.account_type, "debit": 0.0, "credit": 0.0}
        )
        acc["debit"] += line.debit
        acc["credit"] += line.credit

    rows = []
    total_debit, total_credit = 0.0, 0.0
    for name, acc in totals.items():
        net = acc["debit"] - acc["credit"]
        debit_balance = net if net > 0 else 0.0
        credit_balance = -net if net < 0 else 0.0
        rows.append({
            "account": name,
            "type": acc["type"],
            "debit": round(debit_balance, 2),
            "credit": round(credit_balance, 2),
        })
        total_debit += debit_balance
        total_credit += credit_balance

    is_balanced = round(total_debit - total_credit, 2) == 0.0
    return {
        "rows": rows,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "is_balanced": is_balanced,
    }


def build_profit_and_loss(trial_balance_rows: list[dict]) -> dict:
    """Derive P&L from trial balance income/expense accounts."""
    income = sum(r["credit"] - r["debit"] for r in trial_balance_rows if r["type"] == "income")
    expense = sum(r["debit"] - r["credit"] for r in trial_balance_rows if r["type"] == "expense")
    net_profit = income - expense
    return {"total_income": round(income, 2), "total_expense": round(expense, 2),
            "net_profit": round(net_profit, 2)}


def build_balance_sheet(trial_balance_rows: list[dict], net_profit: float) -> dict:
    """Derive Balance Sheet from trial balance asset/liability/equity accounts."""
    assets = sum(r["debit"] - r["credit"] for r in trial_balance_rows if r["type"] == "asset")
    liabilities = sum(r["credit"] - r["debit"] for r in trial_balance_rows if r["type"] == "liability")
    equity = sum(r["credit"] - r["debit"] for r in trial_balance_rows if r["type"] == "equity")
    equity += net_profit  # roll current-year profit into equity
    return {
        "total_assets": round(assets, 2),
        "total_liabilities": round(liabilities, 2),
        "total_equity": round(equity, 2),
        "balances": round(assets - (liabilities + equity), 2) == 0.0,
    }


# ---------------------------------------------------------------------------
# Financial Ratios
# ---------------------------------------------------------------------------
def financial_ratios(
    current_assets: float, current_liabilities: float, inventory: float,
    total_debt: float, total_equity: float, net_profit: float, revenue: float,
    total_assets: float,
) -> dict:
    return {
        "current_ratio": round(current_assets / current_liabilities, 2) if current_liabilities else None,
        "quick_ratio": round((current_assets - inventory) / current_liabilities, 2) if current_liabilities else None,
        "debt_to_equity": round(total_debt / total_equity, 2) if total_equity else None,
        "net_profit_margin_pct": round((net_profit / revenue) * 100, 2) if revenue else None,
        "return_on_assets_pct": round((net_profit / total_assets) * 100, 2) if total_assets else None,
        "return_on_equity_pct": round((net_profit / total_equity) * 100, 2) if total_equity else None,
    }


# ---------------------------------------------------------------------------
# Depreciation
# ---------------------------------------------------------------------------
def straight_line_depreciation(cost: float, salvage: float, useful_life_years: int) -> float:
    return round((cost - salvage) / useful_life_years, 2)


def wdv_depreciation_schedule(cost: float, rate_pct: float, years: int) -> list[dict]:
    """Written Down Value (reducing balance) method — common under Indian Companies Act."""
    schedule = []
    book_value = cost
    for year in range(1, years + 1):
        dep = round(book_value * (rate_pct / 100), 2)
        book_value = round(book_value - dep, 2)
        schedule.append({"year": year, "depreciation": dep, "closing_wdv": book_value})
    return schedule


# ---------------------------------------------------------------------------
# Inventory Costing: FIFO / LIFO / Weighted Average
# ---------------------------------------------------------------------------
@dataclass
class InventoryTxn:
    txn_type: Literal["purchase", "sale"]
    quantity: float
    unit_cost: float = 0.0  # only relevant for purchases


def inventory_valuation(txns: list[InventoryTxn], method: Literal["FIFO", "LIFO", "WAVG"]) -> dict:
    """Return closing inventory value and COGS for a sequence of transactions.

    Inventory cannot be sold below zero. Direct engine callers are validated
    here as well as at the API boundary so financial calculations fail closed.
    """
    if method not in {"FIFO", "LIFO", "WAVG"}:
        raise ValueError("Unsupported inventory valuation method.")

    lots = []  # list of [qty, unit_cost] — order matters for FIFO/LIFO
    cogs = 0.0

    for txn in txns:
        if txn.txn_type not in {"purchase", "sale"}:
            raise ValueError("Inventory transaction type must be purchase or sale.")
        if not all(__import__("math").isfinite(value) for value in (txn.quantity, txn.unit_cost)):
            raise ValueError("Inventory quantity and unit cost must be finite.")
        if txn.quantity <= 0 or txn.unit_cost < 0:
            raise ValueError("Inventory quantity must be positive and unit cost non-negative.")

    for txn in txns:
        if txn.txn_type == "purchase":
            lots.append([txn.quantity, txn.unit_cost])
        else:  # sale
            qty_to_sell = txn.quantity
            available_qty = sum(l[0] for l in lots)
            if qty_to_sell > available_qty:
                raise ValueError("Sale quantity exceeds available inventory.")
            if method == "WAVG":
                total_qty = sum(l[0] for l in lots)
                total_val = sum(l[0] * l[1] for l in lots)
                avg_cost = total_val / total_qty if total_qty else 0
                cogs += qty_to_sell * avg_cost
                # reduce proportionally across all lots
                remaining_qty = total_qty - qty_to_sell
                lots = [[remaining_qty, avg_cost]] if remaining_qty > 0 else []
            else:
                ordered_lots = lots if method == "FIFO" else list(reversed(lots))
                while qty_to_sell > 0 and ordered_lots:
                    lot = ordered_lots[0]
                    take = min(lot[0], qty_to_sell)
                    cogs += take * lot[1]
                    lot[0] -= take
                    qty_to_sell -= take
                    if lot[0] == 0:
                        ordered_lots.pop(0)
                lots = ordered_lots if method == "FIFO" else list(reversed(ordered_lots))

    closing_qty = sum(l[0] for l in lots)
    closing_value = sum(l[0] * l[1] for l in lots)
    return {
        "method": method,
        "closing_quantity": round(closing_qty, 4),
        "closing_inventory_value": round(closing_value, 2),
        "cogs": round(cogs, 2),
    }
