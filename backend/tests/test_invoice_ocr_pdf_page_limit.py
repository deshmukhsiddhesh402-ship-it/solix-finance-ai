"""Regression tests for limiting OCR PDF rasterization to the used page."""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.routers.invoice_ocr as ocr


class PdfUpload:
    filename = "invoice.pdf"

    async def read(self, size=-1):
        return b"%PDF-1.7 test document"


def test_pdf_extraction_renders_only_first_page(monkeypatch):
    calls = []

    def fake_render(data, *, max_pages):
        calls.append(max_pages)
        return [b"rendered-first-page"]

    monkeypatch.setattr(ocr, "pdf_pages_to_images", fake_render)
    monkeypatch.setattr(ocr, "_extract_single_image", lambda data, media_type: {"vendor_name": "Example"})

    result = asyncio.run(ocr.extract_invoice(
        file=PdfUpload(),
        org_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
    ))

    assert calls == [1]
    assert result["invoice"]["vendor_name"] == "Example"
    ocr._EXTRACTED_INVOICES.pop(result["session_id"], None)
