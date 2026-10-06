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
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    zoom = dpi / 72  # PDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)
    for page in list(doc)[:max_pages]:
        pix = page.get_pixmap(matrix=matrix)
        images.append(pix.tobytes("png"))
    return images


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
def invoice_to_journal_lines(invoice: dict, expense_account: str = "Purchases") -> list[dict]:
    """Standard purchase-invoice journal entry:
        Dr Purchases/Expense       (taxable value)
        Dr Input CGST              (if any)
        Dr Input SGST              (if any)
        Dr Input IGST              (if any)
        Cr Vendor (Accounts Payable) (total amount)
    Rounds to 2dp and asserts the entry balances before returning it.
    """
    taxable = round(float(invoice.get("taxable_value") or 0), 2)
    cgst = round(float(invoice.get("cgst_amount") or 0), 2)
    sgst = round(float(invoice.get("sgst_amount") or 0), 2)
    igst = round(float(invoice.get("igst_amount") or 0), 2)
    total = round(float(invoice.get("total_amount") or (taxable + cgst + sgst + igst)), 2)

    vendor = invoice.get("vendor_name") or "Unknown Vendor"

    lines = [{"account_name": expense_account, "account_type": "expense", "debit": taxable, "credit": 0.0}]
    if cgst:
        lines.append({"account_name": "Input CGST", "account_type": "asset", "debit": cgst, "credit": 0.0})
    if sgst:
        lines.append({"account_name": "Input SGST", "account_type": "asset", "debit": sgst, "credit": 0.0})
    if igst:
        lines.append({"account_name": "Input IGST", "account_type": "asset", "debit": igst, "credit": 0.0})
    lines.append({"account_name": f"{vendor} (Payable)", "account_type": "liability", "debit": 0.0, "credit": total})

    total_debit = round(sum(l["debit"] for l in lines), 2)
    total_credit = round(sum(l["credit"] for l in lines), 2)
    if abs(total_debit - total_credit) > 0.01:
        raise ValueError(
            f"Journal entry doesn't balance (Dr {total_debit} vs Cr {total_credit}) — "
            "the extracted taxable_value + tax amounts likely don't add up to total_amount. "
            "Review the extracted fields before posting."
        )
    return lines
