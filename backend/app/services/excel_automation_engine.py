"""
Module 8: Excel Automation engine — real pandas-based data cleaning.

Covers: auto-clean, remove duplicates, merge sheets, detect errors, and
rule-based expense auto-categorization. OCR/invoice-reading (image-based
PDFs, scanned receipts) is a separate, larger sub-system (needs a vision
model or OCR engine) and is intentionally not bundled into this pass —
flagged in the README as still open.
"""
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# Auto-clean
# ---------------------------------------------------------------------------
def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Standard cleanup pass: drop fully-empty rows/columns, strip whitespace
    from string cells, normalize column headers, and coerce obvious numeric
    strings (e.g. "1,200.50", "₹500") into numbers.
    Returns (cleaned_df, report) where report summarizes what changed.
    """
    original_shape = df.shape
    report = {}

    # Normalize headers: strip whitespace, collapse internal spaces.
    df.columns = [str(c).strip() for c in df.columns]

    # Drop fully-empty rows and columns.
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    report["empty_rows_removed"] = original_shape[0] - df.shape[0]
    report["empty_columns_removed"] = original_shape[1] - df.shape[1]

    # Strip whitespace from string/object columns.
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    # Try to coerce currency-like strings (e.g. "₹1,200.50", "1,200") to floats.
    coerced_columns = []
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().astype(str).head(20)
        looks_numeric = sample.str.replace(r"[₹$,\s]", "", regex=True).str.match(r"^-?\d+(\.\d+)?$").mean() if len(sample) else 0
        if looks_numeric > 0.8:
            df[col] = df[col].astype(str).str.replace(r"[₹$,\s]", "", regex=True)
            df[col] = pd.to_numeric(df[col], errors="coerce")
            coerced_columns.append(col)
    report["columns_coerced_to_numeric"] = coerced_columns

    report["final_shape"] = list(df.shape)
    return df, report


# ---------------------------------------------------------------------------
# Remove duplicates
# ---------------------------------------------------------------------------
def remove_duplicates(df: pd.DataFrame, subset: list[str] | None = None) -> tuple[pd.DataFrame, int]:
    before = len(df)
    deduped = df.drop_duplicates(subset=subset, keep="first")
    return deduped, before - len(deduped)


# ---------------------------------------------------------------------------
# Merge sheets
# ---------------------------------------------------------------------------
def merge_sheets(dataframes: list[pd.DataFrame], how: str = "concat") -> pd.DataFrame:
    """Merge multiple sheets/files into one.
    'concat' stacks rows (requires same/similar columns) — the common case
    for merging monthly exports of the same report.
    """
    if how == "concat":
        return pd.concat(dataframes, ignore_index=True, sort=False)
    raise ValueError(f"Unsupported merge strategy: {how}")


# ---------------------------------------------------------------------------
# Error detection
# ---------------------------------------------------------------------------
def detect_errors(df: pd.DataFrame) -> dict:
    """Flag common data-quality issues: missing values, negative values in
    columns that look like amounts, and statistical outliers (values > 3
    standard deviations from the column mean).
    """
    issues = {"missing_values": {}, "negative_amounts": {}, "outliers": {}}

    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing > 0:
            issues["missing_values"][col] = missing

    for col in df.select_dtypes(include=[np.number]).columns:
        neg_count = int((df[col] < 0).sum())
        if neg_count > 0 and any(k in col.lower() for k in ["amount", "value", "price", "revenue", "cost", "salary"]):
            issues["negative_amounts"][col] = neg_count

        series = df[col].dropna()
        if len(series) > 5:
            mean, std = series.mean(), series.std()
            if std > 0:
                outliers = series[(series - mean).abs() > 3 * std]
                if len(outliers) > 0:
                    issues["outliers"][col] = len(outliers)

    return issues


# ---------------------------------------------------------------------------
# Rule-based expense auto-categorization
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "Salaries & Wages": ["salary", "payroll", "wages", "bonus"],
    "Rent": ["rent", "lease"],
    "Utilities": ["electricity", "water bill", "internet", "broadband", "gas bill"],
    "Travel": ["uber", "ola", "flight", "taxi", "airfare", "irctc", "train"],
    "Office Supplies": ["stationery", "printer", "office supplies", "courier"],
    "Marketing": ["advertisement", "marketing", "facebook ads", "google ads", "campaign"],
    "Professional Fees": ["legal fee", "audit fee", "consultant", "professional fee", "ca fee"],
    "Bank Charges": ["bank charge", "processing fee", "neft charge", "service charge"],
    "Software & Subscriptions": ["subscription", "saas", "license", "aws", "azure", "software"],
    "Insurance": ["insurance", "premium"],
}


def categorize_expense(description: str) -> str:
    """Keyword-match a transaction description to a spend category.
    Deterministic, explainable, and free to run at any scale — a good
    default before falling back to an LLM call for genuinely ambiguous rows.
    """
    text = (description or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "Uncategorized"


def auto_categorize_expenses(df: pd.DataFrame, description_column: str) -> pd.DataFrame:
    if description_column not in df.columns:
        raise ValueError(f"Column '{description_column}' not found in data")
    df = df.copy()
    df["category"] = df[description_column].apply(categorize_expense)
    return df
