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
    if not isinstance(gstin, str) or not gstin.strip():
        return False
    return bool(GSTIN_PATTERN.fullmatch(gstin.strip().upper()))


def extract_state_code(gstin: str) -> str | None:
    """First 2 digits of a structurally valid GSTIN are the GST state code."""
    if not is_valid_gstin_format(gstin):
        return None
    return gstin.strip()[:2]


# ---------------------------------------------------------------------------
# PDF -> image rasterization (for scanned/image-based invoice PDFs)
# ---------------------------------------------------------------------------
MAX_PDF_RENDER_DPI = 300
MAX_PDF_RENDER_PAGES = 20
MAX_PDF_PAGE_PIXELS = 20_000_000


def pdf_pages_to_images(pdf_bytes: bytes, dpi: int = 200, max_pages: int = 20) -> list[bytes]:
    """Rasterize a bounded number of PDF pages to PNG images.

    Reject extreme render settings and oversized page dimensions before
    allocating a pixel buffer. The input file-size limit alone cannot prevent
    a tiny PDF from declaring an enormous page size.
    """
    import fitz  # PyMuPDF — local import: only needed on this path
    if not isinstance(dpi, int) or isinstance(dpi, bool) or dpi <= 0 or dpi > MAX_PDF_RENDER_DPI:
        raise ValueError(f"DPI must be between 1 and {MAX_PDF_RENDER_DPI} (DPI must be positive).")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or max_pages <= 0 or max_pages > MAX_PDF_RENDER_PAGES:
        raise ValueError(f"max_pages must be between 1 and {MAX_PDF_RENDER_PAGES}; max_pages must be positive.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    zoom = dpi / 72  # PDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)
    try:
        # islice bounds iteration itself; list(doc) would materialize every page
        # before slicing, defeating the page-count resource limit on huge PDFs.
        from itertools import islice
        for page in islice(doc, max_pages):
            rect = page.rect
            width_px = rect.width * zoom
            height_px = rect.height * zoom
            if width_px <= 0 or height_px <= 0 or width_px * height_px > MAX_PDF_PAGE_PIXELS:
                raise ValueError("PDF page dimensions exceed the supported rendering limit.")
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
def _excel_cell(value):
    """Keep untrusted OCR values compatible with Excel's scalar cell model."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        # Excel cells have a 32,767-character limit. Prefix formula-like
        # untrusted text with an apostrophe so spreadsheet apps treat it as
        # data rather than a formula when a user opens the exported workbook.
        text = value[:32767]
        if text.lstrip()[:1] in ("=", "+", "-", "@"):
            return "'" + text[:32766]
        return text
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return None


def invoices_to_excel(invoices: list[dict]) -> bytes:
    """Flatten extracted invoices to Excel without trusting AI-returned field types."""
    rows = []
    for inv in invoices:
        if not isinstance(inv, dict):
            continue
        gstin = inv.get("vendor_gstin")
        line_items = inv.get("line_items")
        rows.append({
            "Vendor Name": _excel_cell(inv.get("vendor_name")),
            "Vendor GSTIN": _excel_cell(gstin) if isinstance(gstin, str) else None,
            "GSTIN Valid": is_valid_gstin_format(gstin) if isinstance(gstin, str) else False,
            "Invoice Number": _excel_cell(inv.get("invoice_number")),
            "Invoice Date": _excel_cell(inv.get("invoice_date")),
            "Taxable Value": _excel_cell(inv.get("taxable_value")),
            "CGST": _excel_cell(inv.get("cgst_amount")),
            "SGST": _excel_cell(inv.get("sgst_amount")),
            "IGST": _excel_cell(inv.get("igst_amount")),
            "Total Amount": _excel_cell(inv.get("total_amount")),
            "Line Items": len(line_items) if isinstance(line_items, list) else 0,
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
def _invoice_amount(value, field_name: str) -> float:
    """Convert an extracted amount safely; AI output is untrusted input."""
    if isinstance(value, bool):
        raise ValueError(f"Invoice amount {field_name} must be numeric, not boolean.")
    if value is None or value == "":
        return 0.0
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"Invoice amount {field_name} must be numeric.") from exc
    if not math.isfinite(amount):
        raise ValueError(f"Invoice amount {field_name} must be finite.")
    amount = round(amount, 2)
    if not math.isfinite(amount):
        raise ValueError(f"Invoice amount {field_name} must be finite.")
    if amount < 0:
        raise ValueError(f"Invoice amount {field_name} cannot be negative.")
    return amount


def invoice_to_journal_lines(invoice: dict, expense_account: str = "Purchases") -> list[dict]:
    """Build a balanced purchase journal only from finite, nonnegative amounts."""
    if not isinstance(invoice, dict):
        raise ValueError("Invoice data must be an object.")
    if not isinstance(expense_account, str) or not expense_account.strip():
        raise ValueError("Expense account must be a non-empty name.")

    taxable = _invoice_amount(invoice.get("taxable_value"), "taxable_value")
    cgst = _invoice_amount(invoice.get("cgst_amount"), "cgst_amount")
    sgst = _invoice_amount(invoice.get("sgst_amount"), "sgst_amount")
    igst = _invoice_amount(invoice.get("igst_amount"), "igst_amount")

    # An invoice should use either intra-state tax components (CGST/SGST)
    # or inter-state IGST, not both. OCR can misread nearby tax columns, so
    # block ambiguous mixed-tax data before generating accounting entries.
    if igst > 0 and (cgst > 0 or sgst > 0):
        raise ValueError(
            "Invoice tax fields contain both IGST and CGST/SGST. "
            "Review the extracted tax fields before generating journal lines."
        )
    # For an intra-state taxable purchase, CGST and SGST are the two equal
    # halves of the same GST rate. OCR column drift can leave one half missing
    # or assign different amounts; don't silently post that as a valid entry.
    if (cgst > 0 or sgst > 0) and abs(cgst - sgst) > 0.01:
        raise ValueError(
            "CGST and SGST amounts do not match. "
            "Review the extracted intra-state tax fields before generating journal lines."
        )

    supplied_total = invoice.get("total_amount")
    total = (
        round(taxable + cgst + sgst + igst, 2)
        if supplied_total is None or supplied_total == ""
        else _invoice_amount(supplied_total, "total_amount")
    )

    expected_total = round(taxable + cgst + sgst + igst, 2)
    if not math.isfinite(expected_total):
        raise ValueError("Combined invoice amounts exceed the supported numeric range.")
    if abs(expected_total - total) > 0.01:
        raise ValueError(
            f"Extracted invoice total does not reconcile (expected {expected_total}, got {total}). "
            "Review the extracted fields before posting."
        )

    vendor_value = invoice.get("vendor_name")
    if vendor_value is None or vendor_value == "":
        vendor = "Unknown Vendor"
    elif not isinstance(vendor_value, str):
        raise ValueError("Invoice vendor name must be text.")
    else:
        vendor = vendor_value.strip()
        if not vendor:
            vendor = "Unknown Vendor"
        if len(vendor) > 255:
            raise ValueError("Invoice vendor name cannot exceed 255 characters.")

    lines = [{"account_name": expense_account.strip(), "account_type": "expense", "debit": taxable, "credit": 0.0}]
    if cgst:
        lines.append({"account_name": "Input CGST", "account_type": "asset", "debit": cgst, "credit": 0.0})
    if sgst:
        lines.append({"account_name": "Input SGST", "account_type": "asset", "debit": sgst, "credit": 0.0})
    if igst:
        lines.append({"account_name": "Input IGST", "account_type": "asset", "debit": igst, "credit": 0.0})
    lines.append({"account_name": f"{vendor} (Payable)", "account_type": "liability", "debit": 0.0, "credit": total})

    total_debit = round(sum(l["debit"] for l in lines), 2)
    total_credit = round(sum(l["credit"] for l in lines), 2)
    if not math.isfinite(total_debit) or not math.isfinite(total_credit):
        raise ValueError("Journal totals exceed the supported numeric range.")
    if abs(total_debit - total_credit) > 0.01:
        raise ValueError(
            f"Journal entry doesn't balance (Dr {total_debit} vs Cr {total_credit}) — "
            "the extracted taxable_value + tax amounts likely don't add up to total_amount. "
            "Review the extracted fields before posting."
        )
    return lines
