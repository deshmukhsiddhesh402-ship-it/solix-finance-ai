"""Module: OCR & Invoice Processing — tenant-scoped API."""
import json, re, uuid, io
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.services.claude_service import ask_claude_with_image, INVOICE_EXTRACTION_SYSTEM_PROMPT
from app.services.invoice_ocr_engine import pdf_pages_to_images, encode_image_base64, is_valid_gstin_format, invoices_to_excel, invoice_to_journal_lines
from app.routers.enterprise import require_permission

router = APIRouter()
_EXTRACTED_INVOICES: dict[str, dict] = {}
IMAGE_MEDIA_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
MAX_INVOICE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20

def _has_expected_file_signature(file_bytes: bytes, extension: str) -> bool:
    """Reject extension/content mismatches before invoking PDF/image processing."""
    signatures = {
        "pdf": lambda b: b.startswith(b"%PDF-"),
        "jpg": lambda b: b.startswith(b"\xff\xd8\xff"),
        "jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
        "png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
        "webp": lambda b: len(b) >= 12 and b[:4] == b"RIFF" and b[8:12] == b"WEBP",
    }
    checker = signatures.get(extension)
    return bool(checker and checker(file_bytes))


def _strip_json_fences(text: str) -> str:
    return text.strip().replace(chr(96) * 3 + "json", "").replace(chr(96) * 3, "").strip()

def _extract_single_image(image_bytes: bytes, media_type: str) -> dict:
    raw = ask_claude_with_image(INVOICE_EXTRACTION_SYSTEM_PROMPT, "Extract the invoice fields from this document image.", encode_image_base64(image_bytes), media_type, max_tokens=1500)
    try:
        data = json.loads(_strip_json_fences(raw))
    except json.JSONDecodeError as exc:
        raise HTTPException(502, detail="Could not parse the extracted invoice data. Try a clearer image.") from exc
    if data.get("vendor_gstin"):
        data["gstin_format_valid"] = is_valid_gstin_format(data["vendor_gstin"])
    return data

@router.post("/extract-invoice")
async def extract_invoice(file: UploadFile = File(...), org_id: str = Query(...), user_id: str = Depends(require_permission("invoice_ocr", "create"))):
    try:
        org_uuid, user_uuid = uuid.UUID(org_id), uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or user identifier.") from exc
    file_bytes = await file.read()
    lower = (file.filename or "").lower()
    if len(file_bytes) > MAX_INVOICE_BYTES:
        raise HTTPException(413, detail="Invoice file exceeds the 10 MB limit.")
    extension = lower.rsplit(".", 1)[-1] if "." in lower else ""
    if extension not in {"jpg", "jpeg", "png", "webp", "pdf"}:
        raise HTTPException(400, detail="Only .jpg, .png, .webp, and .pdf invoice files are supported.")
    if not _has_expected_file_signature(file_bytes, extension):
        raise HTTPException(400, detail="Invoice file content does not match its file type.")
    if extension == "pdf":
        try:
            images = pdf_pages_to_images(file_bytes, max_pages=MAX_PDF_PAGES)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(422, detail="Could not process the uploaded PDF.") from exc
        if not images: raise HTTPException(422, detail="Could not render any pages from this PDF.")
        extracted = _extract_single_image(images[0], "image/png")
    else:
        extracted = _extract_single_image(file_bytes, IMAGE_MEDIA_TYPES[extension])
    session_id = str(uuid.uuid4())
    _EXTRACTED_INVOICES[session_id] = {"invoice": extracted, "org_id": str(org_uuid), "user_id": str(user_uuid)}
    return {"session_id": session_id, "invoice": extracted}

class JournalEntryRequest(BaseModel):
    session_id: str
    expense_account: str = Field(default="Purchases", min_length=1, max_length=255)

def _get_session(session_id: str, org_id: str, user_id: str) -> dict:
    try:
        session_uuid = uuid.UUID(str(session_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid invoice session identifier.") from exc
    session = _EXTRACTED_INVOICES.get(str(session_uuid))
    if not session: raise HTTPException(404, detail="Session not found. Extract an invoice first.")
    try:
        org_uuid = uuid.UUID(str(org_id))
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or user identifier.") from exc
    if session["org_id"] != str(org_uuid):
        raise HTTPException(403, detail="Invoice session does not belong to this organization.")
    if session["user_id"] != str(user_uuid):
        raise HTTPException(403, detail="Invoice session does not belong to this user.")
    return session

@router.post("/to-journal-entry")
def to_journal_entry(req: JournalEntryRequest, org_id: str = Query(...), _user: str = Depends(require_permission("invoice_ocr", "view"))):
    session = _get_session(req.session_id, org_id, _user)
    try: lines = invoice_to_journal_lines(session["invoice"], req.expense_account)
    except ValueError as exc: raise HTTPException(422, detail=str(exc)) from exc
    return {"journal_lines": lines}

@router.get("/export/{session_id}")
def export_to_excel(session_id: str, org_id: str = Query(...), _user: str = Depends(require_permission("invoice_ocr", "view"))):
    session = _get_session(session_id, org_id, _user)
    return StreamingResponse(io.BytesIO(invoices_to_excel([session["invoice"]])), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=solix_extracted_invoices.xlsx"})