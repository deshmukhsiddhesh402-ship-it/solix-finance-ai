"""
Module 2: Accounting core engine — pure calculation functions, no I/O.
Kept framework-free so they're independently unit-testable and reusable
from CLI scripts, notebooks, or the API router.
"""
from dataclasses import dataclass
from typing import Literal
import math


# ---------------------------------------------------------------------------
# Trial Balance
# ---------------------------------------------------------------------------
@dataclass
class LedgerLine:
    account_name: str
    account_type: Literal["asset", "liability", "equity", "income", "expense"]
    debit: float = 0.0
    credit: float = 0.0


def _validate_finite_numeric(value: object, label: str) -> None:
    """Reject booleans, non-numeric values, and values that overflow float checks."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number.")
    try:
        valid = math.isfinite(value)
    except (OverflowError, TypeError):
        valid = False
    if not valid:
        raise ValueError(f"{label} must be a finite number.")


def _validate_ledger_amount(value: object, label: str) -> None:
    """Compatibility wrapper for ledger amount validation."""
    _validate_finite_numeric(value, label)


def build_trial_balance(lines: list[LedgerLine]) -> dict:
    """Aggregate ledger lines by account and return a trial balance.
    Raises ValueError if total debits != total credits (books don't balance).
    """
    totals: dict[str, dict] = {}
    for line in lines:
        if not isinstance(line, LedgerLine):
            raise ValueError("Trial balance lines must be LedgerLine objects.")
        if not isinstance(line.account_name, str) or not line.account_name.strip():
            raise ValueError("Account name must be non-empty.")
        if line.account_type not in {"asset", "liability", "equity", "income", "expense"}:
            raise ValueError("Invalid account type.")
        _validate_ledger_amount(line.debit, "Debit amount")
        _validate_ledger_amount(line.credit, "Credit amount")
        if line.debit < 0 or line.credit < 0:
            raise ValueError("Debit and credit amounts cannot be negative.")
        acc = totals.setdefault(
            line.account_name, {"type": line.account_type, "debit": 0.0, "credit": 0.0}
        )
        if acc["type"] != line.account_type:
            raise ValueError("Account cannot have multiple account types.")
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


def _validate_trial_balance_rows(trial_balance_rows: list[dict]) -> None:
    """Validate rows before financial statements consume them directly."""
    valid_types = {"asset", "liability", "equity", "income", "expense"}
    for row in trial_balance_rows:
        if not isinstance(row, dict):
            raise ValueError("Trial balance rows must be objects.")
        if row.get("type") not in valid_types:
            raise ValueError("Trial balance row has an invalid account type.")
        for field in ("debit", "credit"):
            value = row.get(field)
            try:
                _validate_finite_numeric(value, "Trial balance amount")
            except ValueError as exc:
                raise ValueError("Trial balance amounts must be finite numbers.") from exc
            if value < 0:
                raise ValueError("Trial balance amounts cannot be negative.")


def build_profit_and_loss(trial_balance_rows: list[dict]) -> dict:
    """Derive P&L from trial balance income/expense accounts."""
    _validate_trial_balance_rows(trial_balance_rows)
    income = sum(r["credit"] - r["debit"] for r in trial_balance_rows if r["type"] == "income")
    expense = sum(r["debit"] - r["credit"] for r in trial_balance_rows if r["type"] == "expense")
    net_profit = income - expense
    return {"total_income": round(income, 2), "total_expense": round(expense, 2),
            "net_profit": round(net_profit, 2)}


def build_balance_sheet(trial_balance_rows: list[dict], net_profit: float) -> dict:
    """Derive Balance Sheet from trial balance asset/liability/equity accounts."""
    _validate_trial_balance_rows(trial_balance_rows)
    try:
        _validate_finite_numeric(net_profit, "Net profit")
    except ValueError as exc:
        raise ValueError("Net profit must be a finite number.") from exc
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
    values = {
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "inventory": inventory,
        "total_debt": total_debt,
        "total_equity": total_equity,
        "net_profit": net_profit,
        "revenue": revenue,
        "total_assets": total_assets,
    }
    for name, value in values.items():
        _validate_finite_numeric(value, f"Financial ratio {name}")
    if any(v < 0 for v in (current_assets, current_liabilities, inventory, total_debt, total_equity, revenue, total_assets)):
        raise ValueError("Financial ratio balance inputs cannot be negative.")
    if inventory > current_assets:
        raise ValueError("Inventory cannot exceed current assets.")
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
    _validate_finite_numeric(cost, "Depreciation cost")
    _validate_finite_numeric(salvage, "Depreciation salvage")
    if isinstance(useful_life_years, bool) or not isinstance(useful_life_years, int):
        raise ValueError("useful_life_years must be a positive integer.")
    if cost < 0 or salvage < 0:
        raise ValueError("cost and salvage cannot be negative.")
    if salvage > cost:
        raise ValueError("salvage cannot exceed cost.")
    if useful_life_years < 1:
        raise ValueError("useful_life_years must be at least 1.")
    return round((cost - salvage) / useful_life_years, 2)


def wdv_depreciation_schedule(cost: float, rate_pct: float, years: int) -> list[dict]:
    """Written Down Value (reducing balance) method — common under Indian Companies Act."""
    _validate_finite_numeric(cost, "WDV cost")
    _validate_finite_numeric(rate_pct, "WDV rate")
    if cost < 0 or rate_pct <= 0 or rate_pct > 100:
        raise ValueError("cost must be non-negative and rate_pct must be between 0 and 100.")
    if isinstance(years, bool) or not isinstance(years, int) or years < 1:
        raise ValueError("years must be a positive integer.")
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
        _validate_finite_numeric(txn.quantity, "Inventory quantity")
        _validate_finite_numeric(txn.unit_cost, "Inventory unit cost")
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
