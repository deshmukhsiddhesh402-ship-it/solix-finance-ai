import asyncio
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.invoice_ocr as ocr


ORG_ID = "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"
USER_ID = "11111111-1111-4111-8111-111111111111"


def test_multipage_pdf_is_rejected_instead_of_silently_extracting_page_one(monkeypatch):
    seen = {}

    def render(_pdf, max_pages):
        seen["max_pages"] = max_pages
        return [b"page-one", b"page-two"]

    def should_not_extract(*_args):
        raise AssertionError("partial invoice extraction must not run")

    monkeypatch.setattr(ocr, "pdf_pages_to_images", render)
    monkeypatch.setattr(ocr, "_extract_single_image", should_not_extract)
    upload = SimpleNamespace(filename="invoice.pdf", read=lambda: None)

    async def read():
        return b"%PDF-test"

    upload.read = read

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ocr.extract_invoice(upload, ORG_ID, USER_ID))

    assert exc.value.status_code == 422
    assert "Multi-page PDF invoices" in exc.value.detail
    assert seen["max_pages"] == 2


def test_single_page_pdf_still_extracts(monkeypatch):
    monkeypatch.setattr(ocr, "pdf_pages_to_images", lambda _pdf, max_pages: [b"page-one"])
    monkeypatch.setattr(ocr, "_extract_single_image", lambda *_args: {"total_amount": 118})
    upload = SimpleNamespace(filename="invoice.pdf")

    async def read():
        return b"%PDF-test"

    upload.read = read
    result = asyncio.run(ocr.extract_invoice(upload, ORG_ID, USER_ID))
    assert result["invoice"]["total_amount"] == 118
    ocr._EXTRACTED_INVOICES.pop(result["session_id"], None)
