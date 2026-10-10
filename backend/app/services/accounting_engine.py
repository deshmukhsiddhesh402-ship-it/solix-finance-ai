"""
Module 2: Accounting core engine — pure calculation functions, no I/O.
Kept framework-free so they're independently unit-testable and reusable
from CLI scripts, notebooks, or the API router.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal
import math


_CENT = Decimal("0.01")


def _as_decimal(value, label: str) -> Decimal:
    """Convert numeric inputs without importing binary float representation noise."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{label} must be a finite number.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} must be a finite number.") from None
    if not amount.is_finite():
        raise ValueError(f"{label} must be a finite number.")
    return amount


def _quantize_money(value: Decimal) -> Decimal:
    """Round currency to paise using an explicit half-up accounting rule."""
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _money_float(value: Decimal) -> float:
    """Keep the existing JSON/API numeric output shape while calculating in Decimal."""
    return float(_quantize_money(value))


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
    """Aggregate ledger lines using decimal-safe currency arithmetic."""
    totals: dict[str, dict] = {}
    for line in lines:
        if not isinstance(line, LedgerLine):
            raise ValueError("Trial balance lines must be LedgerLine objects.")
        if not line.account_name or not line.account_name.strip():
            raise ValueError("Account name must be non-empty.")
        if line.account_type not in {"asset", "liability", "equity", "income", "expense"}:
            raise ValueError("Invalid account type.")
        debit = _as_decimal(line.debit, "Debit amount")
        credit = _as_decimal(line.credit, "Credit amount")
        if debit < 0 or credit < 0:
            raise ValueError("Debit and credit amounts cannot be negative.")
        acc = totals.setdefault(
            line.account_name,
            {"type": line.account_type, "debit": Decimal("0"), "credit": Decimal("0")},
        )
        if acc["type"] != line.account_type:
            raise ValueError("Account cannot have multiple account types.")
        acc["debit"] += debit
        acc["credit"] += credit

    rows = []
    total_debit, total_credit = Decimal("0"), Decimal("0")
    for name, acc in totals.items():
        net = acc["debit"] - acc["credit"]
        debit_balance = _quantize_money(net if net > 0 else Decimal("0"))
        credit_balance = _quantize_money(-net if net < 0 else Decimal("0"))
        rows.append({
            "account": name,
            "type": acc["type"],
            "debit": float(debit_balance),
            "credit": float(credit_balance),
        })
        total_debit += debit_balance
        total_credit += credit_balance

    total_debit = _quantize_money(total_debit)
    total_credit = _quantize_money(total_credit)
    return {
        "rows": rows,
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "is_balanced": total_debit == total_credit,
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
            if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
                raise ValueError("Trial balance amounts must be finite numbers.")
            amount = _as_decimal(value, "Trial balance amount")
            if amount < 0:
                raise ValueError("Trial balance amounts cannot be negative.")

def build_profit_and_loss(trial_balance_rows: list[dict]) -> dict:
    """Derive P&L using decimal-safe totals and paise rounding."""
    _validate_trial_balance_rows(trial_balance_rows)
    income = sum(
        (_as_decimal(r["credit"], "Credit amount") - _as_decimal(r["debit"], "Debit amount")
         for r in trial_balance_rows if r["type"] == "income"),
        Decimal("0"),
    )
    expense = sum(
        (_as_decimal(r["debit"], "Debit amount") - _as_decimal(r["credit"], "Credit amount")
         for r in trial_balance_rows if r["type"] == "expense"),
        Decimal("0"),
    )
    net_profit = income - expense
    return {
        "total_income": _money_float(income),
        "total_expense": _money_float(expense),
        "net_profit": _money_float(net_profit),
    }

def build_balance_sheet(trial_balance_rows: list[dict], net_profit: float) -> dict:
    """Derive Balance Sheet with decimal-safe aggregation."""
    _validate_trial_balance_rows(trial_balance_rows)
    net_profit_decimal = _as_decimal(net_profit, "Net profit")
    assets = sum(
        (_as_decimal(r["debit"], "Debit amount") - _as_decimal(r["credit"], "Credit amount")
         for r in trial_balance_rows if r["type"] == "asset"),
        Decimal("0"),
    )
    liabilities = sum(
        (_as_decimal(r["credit"], "Credit amount") - _as_decimal(r["debit"], "Debit amount")
         for r in trial_balance_rows if r["type"] == "liability"),
        Decimal("0"),
    )
    equity = sum(
        (_as_decimal(r["credit"], "Credit amount") - _as_decimal(r["debit"], "Debit amount")
         for r in trial_balance_rows if r["type"] == "equity"),
        Decimal("0"),
    )
    equity += net_profit_decimal
    assets = _quantize_money(assets)
    liabilities = _quantize_money(liabilities)
    equity = _quantize_money(equity)
    return {
        "total_assets": float(assets),
        "total_liabilities": float(liabilities),
        "total_equity": float(equity),
        "balances": assets == _quantize_money(liabilities + equity),
    }

# ---------------------------------------------------------------------------
# Financial Ratios
# ---------------------------------------------------------------------------
def financial_ratios(
    current_assets: float, current_liabilities: float, inventory: float,
    total_debt: float, total_equity: float, net_profit: float, revenue: float,
    total_assets: float,
) -> dict:
    values = (current_assets, current_liabilities, inventory, total_debt, total_equity, net_profit, revenue, total_assets)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Financial ratio inputs must be finite.")
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
    """Calculate annual straight-line depreciation with explicit paise rounding."""
    cost_decimal = _as_decimal(cost, "cost")
    salvage_decimal = _as_decimal(salvage, "salvage")
    if cost_decimal < 0 or salvage_decimal < 0:
        raise ValueError("cost and salvage cannot be negative.")
    if salvage_decimal > cost_decimal:
        raise ValueError("salvage cannot exceed cost.")
    if isinstance(useful_life_years, bool) or not isinstance(useful_life_years, int) or useful_life_years < 1:
        raise ValueError("useful_life_years must be a positive integer.")
    annual_depreciation = (cost_decimal - salvage_decimal) / Decimal(useful_life_years)
    return float(_quantize_money(annual_depreciation))


def wdv_depreciation_schedule(cost: float, rate_pct: float, years: int) -> list[dict]:
    """Calculate reducing-balance depreciation with decimal-safe paise rounding."""
    cost_decimal = _as_decimal(cost, "cost")
    rate_decimal = _as_decimal(rate_pct, "rate_pct")
    if cost_decimal < 0 or rate_decimal <= 0 or rate_decimal > 100:
        raise ValueError("cost must be non-negative and rate_pct must be between 0 and 100.")
    if isinstance(years, bool) or not isinstance(years, int) or years < 1:
        raise ValueError("years must be a positive integer.")
    schedule = []
    book_value = _quantize_money(cost_decimal)
    for year in range(1, years + 1):
        dep = _quantize_money(book_value * rate_decimal / Decimal("100"))
        book_value = _quantize_money(book_value - dep)
        schedule.append({"year": year, "depreciation": float(dep), "closing_wdv": float(book_value)})
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
