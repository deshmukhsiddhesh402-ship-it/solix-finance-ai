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
def _invoice_amount(invoice: dict, field: str, *, default=None):
    """Validate and quantize one invoice amount to paise.

    Only absent optional fields may use a default; explicitly supplied None,
    booleans, strings, non-finite values, and amounts above the supported
    15-integer-digit currency range are rejected.
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

    if field not in invoice:
        if default is None:
            raise ValueError(f"Invoice amount '{field}' is required.")
        raw = default
    else:
        raw = invoice[field]

    if isinstance(raw, bool) or not isinstance(raw, (int, float, Decimal)):
        raise ValueError(f"Invoice amount '{field}' must be a finite numeric value.")
    try:
        amount = Decimal(str(raw))
        if not amount.is_finite():
            raise ValueError(f"Invoice amount '{field}' must be finite.")
        if amount < 0:
            raise ValueError(f"Invoice amount '{field}' cannot be negative.")
        if amount > Decimal("999999999999999.99"):
            raise ValueError(f"Invoice amount '{field}' exceeds the supported limit.")
        with localcontext() as context:
            context.prec = max(28, len(amount.as_tuple().digits) + 4)
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return amount
    except (InvalidOperation, OverflowError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("Invoice amount"):
            raise
        raise ValueError(f"Invoice amount '{field}' is invalid or out of range.") from exc


def invoice_to_journal_lines(invoice: dict, expense_account: str = "Purchases") -> list[dict]:
    """Convert a validated purchase invoice into balanced journal lines.

    Currency components and total are rounded to paise with Decimal
    ROUND_HALF_UP. After rounding, totals must reconcile exactly; no
    post-rounding tolerance is allowed for an unbalanced journal entry.
    Missing GST components default to zero and a missing total is derived.
    Explicitly supplied invalid values are never replaced by defaults.
    """
    from decimal import Decimal, ROUND_HALF_UP

    if not isinstance(invoice, dict):
        raise ValueError("Invoice must be a dictionary.")
    if not isinstance(expense_account, str) or not expense_account.strip():
        raise ValueError("Expense account must be a non-empty string.")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in expense_account):
        raise ValueError("Expense account contains unsupported control characters.")

    zero = Decimal("0.00")
    taxable = _invoice_amount(invoice, "taxable_value", default=zero)
    cgst = _invoice_amount(invoice, "cgst_amount", default=zero)
    sgst = _invoice_amount(invoice, "sgst_amount", default=zero)
    igst = _invoice_amount(invoice, "igst_amount", default=zero)
    if "total_amount" in invoice:
        total = _invoice_amount(invoice, "total_amount")
    else:
        total = (taxable + cgst + sgst + igst).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    expected_total = (taxable + cgst + sgst + igst).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    if expected_total != total:
        raise ValueError(
            f"Extracted invoice total does not reconcile (expected {expected_total}, got {total}). "
            "Review the extracted fields before posting."
        )

    vendor_value = invoice.get("vendor_name", "Unknown Vendor")
    if vendor_value is None:
        vendor_value = "Unknown Vendor"
    if not isinstance(vendor_value, str) or not vendor_value.strip():
        raise ValueError("Vendor name must be a non-empty string when provided.")
    vendor = vendor_value.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in vendor):
        raise ValueError("Vendor name contains unsupported control characters.")

    def as_float(value):
        return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    lines = [{
        "account_name": expense_account.strip(),
        "account_type": "expense",
        "debit": as_float(taxable),
        "credit": 0.0,
    }]
    if cgst:
        lines.append({"account_name": "Input CGST", "account_type": "asset", "debit": as_float(cgst), "credit": 0.0})
    if sgst:
        lines.append({"account_name": "Input SGST", "account_type": "asset", "debit": as_float(sgst), "credit": 0.0})
    if igst:
        lines.append({"account_name": "Input IGST", "account_type": "asset", "debit": as_float(igst), "credit": 0.0})
    lines.append({
        "account_name": f"{vendor} (Payable)",
        "account_type": "liability",
        "debit": 0.0,
        "credit": as_float(total),
    })

    total_debit = sum((Decimal(str(line["debit"])) for line in lines), zero)
    total_credit = sum((Decimal(str(line["credit"])) for line in lines), zero)
    if total_debit != total_credit:
        raise ValueError(
            f"Journal entry doesn't balance (Dr {total_debit} vs Cr {total_credit}) — "
            "review the extracted taxable value, tax amounts, and invoice total before posting."
        )
    return lines
