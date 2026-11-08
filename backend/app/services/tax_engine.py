"""
Module 3: Indian Tax engine — GST, TDS, and Income Tax calculators.

NOTE: Tax slabs/rates change with each Union Budget. The constants below
reflect FY 2025-26 (AY 2026-27) new-regime slabs as a sensible default — always
confirm current rates before filing, and expose these as configurable inputs
in the UI rather than hardcoding them permanently.
"""
from dataclasses import dataclass
import math


MAX_GSTR3B_LINES = 5_000


def _require_finite_non_negative(value: float, label: str) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be a finite, non-negative number.")


def _require_rate(value: float, label: str) -> None:
    if not math.isfinite(value) or value < 0 or value > 100:
        raise ValueError(f"{label} must be a finite percentage between 0 and 100.")


def _checked_fsum(values, label: str) -> float:
    """Sum financial values without allowing overflow or non-finite results."""
    try:
        total = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label} exceeds the supported numeric range.") from exc
    if not math.isfinite(total):
        raise ValueError(f"{label} exceeds the supported numeric range.")
    return total


def _checked_round(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{label} exceeds the supported numeric range.")
    rounded = round(value, 2)
    if not math.isfinite(rounded):
        raise ValueError(f"{label} exceeds the supported numeric range.")
    return rounded


# ---------------------------------------------------------------------------
# GST
# ---------------------------------------------------------------------------
def calculate_gst(taxable_value: float, gst_rate_pct: float, is_interstate: bool) -> dict:
    """Split GST into IGST (interstate) or CGST+SGST (intrastate)."""
    _require_finite_non_negative(taxable_value, "taxable_value")
    _require_rate(gst_rate_pct, "gst_rate_pct")
    if not isinstance(is_interstate, bool):
        raise ValueError("is_interstate must be a boolean.")
    total_tax = _checked_round(taxable_value * (gst_rate_pct / 100), "GST amount")
    invoice_total = _checked_round(_checked_fsum((taxable_value, total_tax), "Invoice total"), "Invoice total")
    if is_interstate:
        return {"taxable_value": taxable_value, "igst": total_tax, "cgst": 0.0,
                "sgst": 0.0, "total_tax": total_tax, "invoice_total": invoice_total}
    half = _checked_round(total_tax / 2, "CGST/SGST amount")
    split_total = _checked_round(_checked_fsum((half, half), "Split GST total"), "Split GST total")
    split_invoice_total = _checked_round(_checked_fsum((taxable_value, split_total), "Invoice total"), "Invoice total")
    return {"taxable_value": taxable_value, "igst": 0.0, "cgst": half, "sgst": half,
            "total_tax": split_total, "invoice_total": split_invoice_total}


@dataclass
class GstInvoiceLine:
    taxable_value: float
    gst_rate_pct: float
    is_interstate: bool


def gstr3b_summary(lines: list[GstInvoiceLine], input_tax_credit: float = 0.0) -> dict:
    """Aggregate outward supplies into a bounded GSTR-3B-style summary with ITC set-off."""
    _require_finite_non_negative(input_tax_credit, "input_tax_credit")
    if not isinstance(lines, list):
        raise ValueError("lines must be a list.")
    if len(lines) > MAX_GSTR3B_LINES:
        raise ValueError(f"lines cannot contain more than {MAX_GSTR3B_LINES} entries.")
    if any(not isinstance(line, GstInvoiceLine) for line in lines):
        raise ValueError("Each line must be a GstInvoiceLine.")

    taxable_values = []
    output_taxes = []
    for line in lines:
        result = calculate_gst(line.taxable_value, line.gst_rate_pct, line.is_interstate)
        taxable_values.append(line.taxable_value)
        output_taxes.append(result["total_tax"])

    total_taxable = _checked_round(_checked_fsum(taxable_values, "Total taxable value"), "Total taxable value")
    total_tax = _checked_round(_checked_fsum(output_taxes, "Total output tax"), "Total output tax")
    net_payable = max(0.0, _checked_round(total_tax - input_tax_credit, "Net GST payable"))
    return {
        "total_taxable_value": total_taxable,
        "total_output_tax": total_tax,
        "input_tax_credit_claimed": _checked_round(input_tax_credit, "Input tax credit"),
        "net_gst_payable": net_payable,
    }


# ---------------------------------------------------------------------------
# TDS
# ---------------------------------------------------------------------------
# Common TDS sections and default rates (Income Tax Act) — configurable.
TDS_SECTION_RATES = {
    "192": None,      # Salary — slab rate, computed separately
    "194A": 10.0,     # Interest (other than securities)
    "194C": 1.0,      # Contractor payments (individual/HUF); 2% for others
    "194H": 5.0,      # Commission/brokerage
    "194I": 10.0,     # Rent (land/building/furniture)
    "194J": 10.0,     # Professional/technical services
    "194Q": 0.1,      # Purchase of goods (above threshold)
}


def calculate_tds(amount_paid: float, section: str, has_pan: bool = True) -> dict:
    """Calculate TDS for a payment under a given section.
    If the deductee has no PAN, TDS is charged at 20% flat per Sec 206AA.
    """
    _require_finite_non_negative(amount_paid, "amount_paid")
    if not isinstance(section, str) or not section.strip():
        raise ValueError("section must be a non-empty string.")
    if not isinstance(has_pan, bool):
        raise ValueError("has_pan must be a boolean.")
    rate = TDS_SECTION_RATES.get(section)
    if rate is None:
        raise ValueError(f"Section {section} requires slab-based calculation, not flat rate.")
    effective_rate = 20.0 if not has_pan else rate
    tds_amount = round(amount_paid * (effective_rate / 100), 2)
    return {
        "section": section, "amount_paid": amount_paid, "rate_applied_pct": effective_rate,
        "tds_amount": tds_amount, "net_payment": round(amount_paid - tds_amount, 2),
    }


# ---------------------------------------------------------------------------
# Income Tax (Individuals) — New Regime, FY 2025-26 slabs
# ---------------------------------------------------------------------------
NEW_REGIME_SLABS_FY2025_26 = [
    (400_000, 0.0),
    (800_000, 5.0),
    (1_200_000, 10.0),
    (1_600_000, 15.0),
    (2_000_000, 20.0),
    (2_400_000, 25.0),
    (float("inf"), 30.0),
]

STANDARD_DEDUCTION_NEW_REGIME = 75_000
CESS_PCT = 4.0


def calculate_income_tax_new_regime(gross_salary: float, other_income: float = 0.0) -> dict:
    """Slab-wise income tax under the new regime, with standard deduction,
    Section 87A rebate (nil tax up to ₹12L taxable income), and 4% cess.
    """
    _require_finite_non_negative(gross_salary, "gross_salary")
    _require_finite_non_negative(other_income, "other_income")

    taxable_income = max(0.0, gross_salary - STANDARD_DEDUCTION_NEW_REGIME) + other_income

    tax = 0.0
    lower_bound = 0
    for upper_bound, rate in NEW_REGIME_SLABS_FY2025_26:
        if taxable_income > lower_bound:
            slab_amount = min(taxable_income, upper_bound) - lower_bound
            tax += slab_amount * (rate / 100)
        lower_bound = upper_bound
        if taxable_income <= upper_bound:
            break

    # Section 87A rebate: taxable income up to ₹12,00,000 pays zero tax (new regime).
    rebate_applied = taxable_income <= 1_200_000
    if rebate_applied:
        tax = 0.0

    cess = round(tax * (CESS_PCT / 100), 2)
    total_tax = round(tax + cess, 2)

    return {
        # The current engine constants are explicitly FY 2025-26; surface that
        # basis so callers cannot mistake this result for a newer tax year.
        "financial_year": "2025-26",
        "tax_regime": "new",
        "taxable_income": round(taxable_income, 2),
        "tax_before_cess": round(tax, 2),
        "rebate_87a_applied": rebate_applied,
        "health_education_cess": cess,
        "total_tax_payable": total_tax,
        "effective_tax_rate_pct": round((total_tax / taxable_income) * 100, 2) if taxable_income else 0.0,
    }
