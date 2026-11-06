import pytest
from fastapi import HTTPException

from app.routers import invoice_ocr


def _mock_provider(monkeypatch, response):
    monkeypatch.setattr(
        invoice_ocr,
        "ask_claude_with_image",
        lambda *args, **kwargs: response,
    )


def test_invoice_ocr_rejects_non_text_provider_response(monkeypatch):
    _mock_provider(monkeypatch, {"unexpected": "object"})

    with pytest.raises(HTTPException) as exc:
        invoice_ocr._extract_single_image(b"image", "image/png")

    assert exc.value.status_code == 502


def test_invoice_ocr_rejects_deeply_nested_provider_json(monkeypatch):
    nested_json = "[" * 3_000 + "]" * 3_000
    _mock_provider(monkeypatch, nested_json)

    with pytest.raises(HTTPException) as exc:
        invoice_ocr._extract_single_image(b"image", "image/png")

    assert exc.value.status_code == 502
    assert "Could not parse" in exc.value.detail


def test_invoice_ocr_rejects_malformed_provider_json(monkeypatch):
    _mock_provider(monkeypatch, "{not-json")

    with pytest.raises(HTTPException) as exc:
        invoice_ocr._extract_single_image(b"image", "image/png")

    assert exc.value.status_code == 502


def test_invoice_ocr_rejects_non_object_json_response(monkeypatch):
    _mock_provider(monkeypatch, '["invoice", "fields"]')

    with pytest.raises(HTTPException) as exc:
        invoice_ocr._extract_single_image(b"image", "image/png")

    assert exc.value.status_code == 502


def test_invoice_ocr_returns_valid_invoice_object(monkeypatch):
    _mock_provider(monkeypatch, '{"vendor_name":"Sample Vendor","invoice_number":"INV-1"}')

    result = invoice_ocr._extract_single_image(b"image", "image/png")

    assert result == {"vendor_name": "Sample Vendor", "invoice_number": "INV-1"}
