"""
Module: OCR & Invoice Processing — API layer.

Accepts an image (jpg/png) or PDF invoice/receipt, uses Claude's vision to
extract structured fields, validates the numbers add up, and offers export
to Excel or a ready-to-post accounting journal entry.
"""
import json
import re
import uuid
import io
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.claude_service import ask_claude_with_image, INVOICE_EXTRACTION_SYSTEM_PROMPT
from app.services.invoice_ocr_engine import (
    pdf_pages_to_images, encode_image_base64, is_valid_gstin_format,
    invoices_to_excel, invoice_to_journal_lines,
)

router = APIRouter()

# session_id -> list of extracted invoice dicts (for the export-to-Excel step)
_EXTRACTED_INVOICES: dict[str, list[dict]] = {}

IMAGE_MEDIA_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return text


def _extract_single_image(image_bytes: bytes, media_type: str) -> dict:
    b64 = encode_image_base64(image_bytes)
    raw = ask_claude_with_image(
        INVOICE_EXTRACTION_SYSTEM_PROMPT,
        "Extract the invoice fields from this document image.",
        b64, media_type, max_tokens=1500,
    )
    try:
        data = json.loads(_strip_json_fences(raw))
    except json.JSONDecodeError:
        raise HTTPException(502, detail="Could not parse the extracted invoice data. Try a clearer image.")

    if data.get("vendor_gstin"):
        data["gstin_format_valid"] = is_valid_gstin_format(data["vendor_gstin"])
    return data


@router.post("/extract-invoice")
async def extract_invoice(file: UploadFile = File(...)):
    """Extract structured fields from a single invoice/receipt (image or PDF)."""
    file_bytes = await file.read()
    lower = file.filename.lower()

    if lower.endswith(".pdf"):
        images = pdf_pages_to_images(file_bytes)
        if not images:
            raise HTTPException(422, detail="Could not render any pages from this PDF.")
        # Most invoices are single-page; extract from the first page.
        extracted = _extract_single_image(images[0], "image/png")
    elif any(lower.endswith(f".{ext}") for ext in IMAGE_MEDIA_TYPES):
        ext = lower.rsplit(".", 1)[-1]
        extracted = _extract_single_image(file_bytes, IMAGE_MEDIA_TYPES[ext])
    else:
        raise HTTPException(400, detail="Only .jpg, .png, .webp, and .pdf invoice files are supported.")

    session_id = str(uuid.uuid4())
    _EXTRACTED_INVOICES[session_id] = [extracted]

    return {"session_id": session_id, "invoice": extracted}


class JournalEntryRequest(BaseModel):
    session_id: str
    expense_account: str = "Purchases"


@router.post("/to-journal-entry")
def to_journal_entry(req: JournalEntryRequest):
    invoices = _EXTRACTED_INVOICES.get(req.session_id)
    if not invoices:
        raise HTTPException(404, detail="Session not found. Extract an invoice first.")
    try:
        lines = invoice_to_journal_lines(invoices[0], req.expense_account)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    return {"journal_lines": lines}


@router.get("/export/{session_id}")
def export_to_excel(session_id: str):
    invoices = _EXTRACTED_INVOICES.get(session_id)
    if not invoices:
        raise HTTPException(404, detail="Session not found. Extract an invoice first.")
    xlsx_bytes = invoices_to_excel(invoices)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=solix_extracted_invoices.xlsx"},
    )
