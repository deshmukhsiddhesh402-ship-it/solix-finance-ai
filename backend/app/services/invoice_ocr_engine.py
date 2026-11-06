"""
Module: OCR & Invoice Processing.

APPROACH: uses Claude's vision capability to read invoices/receipts directly
(via claude_service.ask_claude_with_image), rather than a separate OCR
engine like Tesseract. This is a deliberate choice: Claude reads layout,
handwriting, and context (e.g. distinguishing "Invoice No." from "PO No.")
far better than raw OCR text, and returns already-structured data instead
of a blob of text that still needs parsing.

This file holds everything AROUND that vision call that's pure, testable
logic: GSTIN format validation, PDF-page-to-image rasterization (for
scanned/image-based PDF invoices), and exporting extracted invoice data to
Excel or accounting journal entries.
"""
import io
import re
import base64
import math
import pandas as pd

# ---------------------------------------------------------------------------
# GSTIN validation
# ---------------------------------------------------------------------------
# Format: 2-digit state code + 10-char PAN + 1-digit entity code + 'Z' + 1 checksum char.
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")

GSTIN_CHECKSUM_CODEPOINTS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def is_valid_gstin_format(gstin: str) -> bool:
    """Structural validation (regex) — confirms it LOOKS like a GSTIN:
    2-digit state code, 10-char PAN, entity code, 'Z', check character.
    This does NOT verify the check-digit or hit the government GSTN API, so
    it can't catch a single-character typo or confirm the GSTIN is actually
    registered/active. A mod-36 check-digit algorithm exists and a live GSTN
    lookup API exists for that — deliberately not included here: an
    self-implemented checksum validator that hasn't been verified against
    authoritative test vectors is worse than no checksum check at all, since
    it could silently reject genuinely valid GSTINs. Wire the real GSTN
    "Search Taxpayer" API for that when you're ready to go beyond format
    checking (https://www.gst.gov.in — public search, or a paid GSP API for
    programmatic access).
    """
    if not gstin:
        return False
    return bool(GSTIN_PATTERN.match(gstin.strip().upper()))


def extract_state_code(gstin: str) -> str | None:
    """First 2 digits of a valid GSTIN are the GST state code."""
    if not is_valid_gstin_format(gstin):
        return None
    return gstin[:2]


# ---------------------------------------------------------------------------
# PDF -> image rasterization (for scanned/image-based invoice PDFs)
# ---------------------------------------------------------------------------
def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 200, max_pages: int = 20) -> list[bytes]:
    """Rasterize each PDF page to a PNG image (as bytes) using PyMuPDF.
    Needed because scanned invoice PDFs have no extractable text layer —
    Claude's vision has to look at the page as a picture.
    """
    import fitz  # PyMuPDF — local import: only needed on this path
    if dpi <= 0:
        raise ValueError("DPI must be positive.")
    if max_pages <= 0:
        raise ValueError("max_pages must be positive.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    zoom = dpi / 72  # PDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)
    try:
        for page in list(doc)[:max_pages]:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
        return images
    finally:
        doc.close()


def encode_image_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


# ---------------------------------------------------------------------------
# Export extracted invoices to Excel
# ---------------------------------------------------------------------------
def invoices_to_excel(invoices: list[dict]) -> bytes:
    """Flatten a list of extracted invoice dicts into a single-sheet Excel
    file, one row per invoice (line items summarized as a count)."""
    rows = []
    for inv in invoices:
        rows.append({
            "Vendor Name": inv.get("vendor_name"),
            "Vendor GSTIN": inv.get("vendor_gstin"),
            "GSTIN Valid": is_valid_gstin_format(inv.get("vendor_gstin") or ""),
            "Invoice Number": inv.get("invoice_number"),
            "Invoice Date": inv.get("invoice_date"),
            "Taxable Value": inv.get("taxable_value"),
            "CGST": inv.get("cgst_amount"),
            "SGST": inv.get("sgst_amount"),
            "IGST": inv.get("igst_amount"),
            "Total Amount": inv.get("total_amount"),
            "Line Items": len(inv.get("line_items") or []),
        })
    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Invoices")
    buffer.seek(0)
    return buffer.read()


# ---------------------------------------------------------------------------
# Convert extracted invoice to a double-entry journal entry
# ---------------------------------------------------------------------------
def _parse_invoice_amount(value, label: str, default: float = 0.0) -> float:
    """Convert untrusted extracted invoice values into finite non-negative amounts."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return default
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite numeric value.")
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be a finite numeric value.") from exc
    if not math.isfinite(amount):
        raise ValueError(f"{label} must be a finite numeric value.")
    if amount < 0:
        raise ValueError(f"{label} cannot be negative.")
    return round(amount, 2)


def _checked_invoice_sum(values: list[float], label: str) -> float:
    try:
        total = math.fsum(values)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{label} exceeds the supported numeric range.") from exc
    if not math.isfinite(total):
        raise ValueError(f"{label} exceeds the supported numeric range.")
    return round(total, 2)


def invoice_to_journal_lines(invoice: dict, expense_account: str = "Purchases") -> list[dict]:
    """Convert an extracted purchase invoice into a balanced double-entry entry.

    Invalid provider-extracted values are rejected as ValueError so the API can
    return a controlled 422 and never build journal lines from malformed data.
    """
    if not isinstance(invoice, dict):
        raise ValueError("Invoice data must be an object.")
    if not isinstance(expense_account, str) or not expense_account.strip():
        raise ValueError("Expense account must be a non-empty string.")

    taxable = _parse_invoice_amount(invoice.get("taxable_value"), "taxable_value")
    cgst = _parse_invoice_amount(invoice.get("cgst_amount"), "cgst_amount")
    sgst = _parse_invoice_amount(invoice.get("sgst_amount"), "sgst_amount")
    igst = _parse_invoice_amount(invoice.get("igst_amount"), "igst_amount")

    expected_total = _checked_invoice_sum([taxable, cgst, sgst, igst], "Invoice total")
    raw_total = invoice.get("total_amount")
    total = expected_total if raw_total is None or (isinstance(raw_total, str) and not raw_total.strip()) else _parse_invoice_amount(raw_total, "total_amount")
    if abs(expected_total - total) > 0.01:
        raise ValueError(
            f"Extracted invoice total does not reconcile (expected {expected_total}, got {total}). "
            "Review the extracted fields before posting."
        )

    vendor_value = invoice.get("vendor_name")
    vendor = vendor_value.strip() if isinstance(vendor_value, str) and vendor_value.strip() else "Unknown Vendor"

    lines = [{"account_name": expense_account.strip(), "account_type": "expense", "debit": taxable, "credit": 0.0}]
    if cgst:
        lines.append({"account_name": "Input CGST", "account_type": "asset", "debit": cgst, "credit": 0.0})
    if sgst:
        lines.append({"account_name": "Input SGST", "account_type": "asset", "debit": sgst, "credit": 0.0})
    if igst:
        lines.append({"account_name": "Input IGST", "account_type": "asset", "debit": igst, "credit": 0.0})
    lines.append({"account_name": f"{vendor} (Payable)", "account_type": "liability", "debit": 0.0, "credit": total})

    total_debit = _checked_invoice_sum([line["debit"] for line in lines], "Journal debit total")
    total_credit = _checked_invoice_sum([line["credit"] for line in lines], "Journal credit total")
    if abs(total_debit - total_credit) > 0.01:
        raise ValueError(
            f"Journal entry doesn't balance (Dr {total_debit} vs Cr {total_credit}) — "
            "the extracted taxable_value + tax amounts likely don't add up to total_amount. "
            "Review the extracted fields before posting."
        )
    return lines
