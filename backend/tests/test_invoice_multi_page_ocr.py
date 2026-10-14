"""Regression tests for bounded multi-page invoice OCR."""
import json

import pytest
from fastapi import HTTPException

from app.routers import invoice_ocr
from app.services import claude_service


def test_pdf_extraction_sends_multiple_pages_in_one_request(monkeypatch):
    captured = {}

    def fake_call(system_prompt, user_text, images, max_tokens=1500):
        captured["images"] = images
        captured["user_text"] = user_text
        captured["max_tokens"] = max_tokens
        return json.dumps({
            "vendor_name": "Example Supplies",
            "vendor_gstin": None,
            "invoice_number": "INV-12",
            "invoice_date": None,
            "taxable_value": 100,
            "cgst_amount": 9,
            "sgst_amount": 9,
            "igst_amount": 0,
            "total_amount": 118,
            "line_items": [{"description": "Materials", "quantity": 1, "amount": 100}],
            "confidence_notes": "none",
        })

    monkeypatch.setattr(invoice_ocr, "ask_claude_with_images", fake_call)
    result = invoice_ocr._extract_pdf_pages([b"page-one", b"page-two"])

    assert len(captured["images"]) == 2
    assert "all 2 attached page images" in captured["user_text"]
    assert captured["max_tokens"] == 2000
    assert result["invoice_number"] == "INV-12"
    assert result["extraction_pages_processed"] == 2
    assert result["extraction_incomplete"] is False


def test_pdf_extraction_marks_truncated_document_incomplete(monkeypatch):
    monkeypatch.setattr(
        invoice_ocr,
        "ask_claude_with_images",
        lambda *args, **kwargs: json.dumps({
            "vendor_name": "Example",
            "line_items": [],
            "confidence_notes": "none",
        }),
    )

    result = invoice_ocr._extract_pdf_pages([b"page"] * 6)

    assert result["extraction_pages_processed"] == 5
    assert result["extraction_incomplete"] is True
    assert "Only the first 5 pages were processed" in result["confidence_notes"]


def test_incomplete_pdf_is_blocked_from_journal_generation(monkeypatch):
    session_id = "b5a6cfc8-03bb-4b4d-8f0f-6f27d3d3a7a8"
    org_id = "e26b45d0-b18e-4c4b-a9c4-8e4c9e63b842"
    monkeypatch.setitem(invoice_ocr._EXTRACTED_INVOICES, session_id, {
        "invoice": {"extraction_incomplete": True},
        "org_id": org_id,
        "user_id": "4d11b8e8-1f44-4cf0-bb36-21e3e31c5f22",
        "created_at": __import__("time").time(),
    })

    with pytest.raises(HTTPException) as exc_info:
        invoice_ocr.to_journal_entry(
            invoice_ocr.JournalEntryRequest(session_id=session_id),
            org_id=org_id,
            _user="4d11b8e8-1f44-4cf0-bb36-21e3e31c5f22",
        )

    assert exc_info.value.status_code == 422
    assert "first 5 PDF pages" in exc_info.value.detail


def test_multi_image_request_rejects_aggregate_payload_over_limit(monkeypatch):
    monkeypatch.setattr(claude_service, "MAX_CLAUDE_IMAGE_BASE64_CHARS", 5)

    with pytest.raises(ValueError, match="Combined image payload"):
        claude_service.ask_claude_with_images(
            "system",
            "extract",
            [("abc", "image/png"), ("def", "image/png")],
        )


def test_multi_image_request_rejects_more_than_five_images():
    with pytest.raises(ValueError, match="Between 1 and 5"):
        claude_service.ask_claude_with_images(
            "system",
            "extract",
            [("a", "image/png")] * 6,
        )


@pytest.mark.parametrize("vendor_gstin", [123, [], {}, True])
def test_extraction_marks_non_string_gstin_invalid_without_crashing(vendor_gstin):
    result = invoice_ocr._parse_extraction(json.dumps({"vendor_gstin": vendor_gstin}))

    assert result["gstin_format_valid"] is False
