"""Regression tests for bounded multi-page invoice OCR."""
from types import SimpleNamespace

import pytest


def test_claude_multi_image_request_preserves_page_order(monkeypatch):
    import app.services.claude_service as service

    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"vendor_name":"Acme"}')])

    monkeypatch.setattr(
        service,
        "_client",
        SimpleNamespace(messages=SimpleNamespace(create=fake_create)),
    )

    result = service.ask_claude_with_images(
        "system",
        "Read all pages",
        [("cGFnZS0x", "image/png"), ("cGFnZS0y", "image/png")],
    )

    blocks = captured["messages"][0]["content"]
    assert result == '{"vendor_name":"Acme"}'
    assert [block["source"]["data"] for block in blocks if block["type"] == "image"] == [
        "cGFnZS0x",
        "cGFnZS0y",
    ]
    assert blocks[-1] == {"type": "text", "text": "Read all pages"}


@pytest.mark.parametrize(
    "images",
    [
        [],
        [("", "image/png")],
        [("abc", "image/svg+xml")],
        [("x", "image/png")] * 21,
        [("x" * 15_000_001, "image/png")],
    ],
)
def test_claude_multi_image_request_rejects_invalid_or_oversized_payloads(monkeypatch, images):
    import app.services.claude_service as service

    with pytest.raises(ValueError):
        service.ask_claude_with_images("system", "Read all pages", images)


def test_pdf_invoice_extraction_sends_every_rendered_page(monkeypatch):
    import json
    import app.routers.invoice_ocr as router

    captured = {}

    def fake_ask(system_prompt, user_text, images, max_tokens):
        captured["images"] = images
        captured["prompt"] = user_text
        return json.dumps({"vendor_name": "Acme Supplies", "total_amount": 1180})

    monkeypatch.setattr(router, "ask_claude_with_images", fake_ask)

    result = router._extract_multiple_images([b"first-page", b"second-page"])

    import base64

    assert [base64.b64decode(item[0]) for item in captured["images"]] == [
        b"first-page",
        b"second-page",
    ]
    assert "every page" in captured["prompt"]
    assert result["vendor_name"] == "Acme Supplies"


def test_pdf_rasterizer_rejects_truncation_and_closes_document(monkeypatch):
    import sys
    from types import SimpleNamespace
    import app.services.invoice_ocr_engine as engine

    class FakeDocument(list):
        closed = False

        def close(self):
            self.closed = True

    document = FakeDocument([object(), object()])
    fake_fitz = SimpleNamespace(
        open=lambda **kwargs: document,
        Matrix=lambda zoom, zoom_y: (zoom, zoom_y),
    )
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    with pytest.raises(ValueError, match="2-page limit"):
        engine.pdf_pages_to_images(b"%PDF-test", max_pages=1)

    assert document.closed is True


def test_pdf_rasterizer_renders_all_pages_within_limit(monkeypatch):
    import sys
    from types import SimpleNamespace
    import app.services.invoice_ocr_engine as engine

    class FakePixmap:
        def __init__(self, payload):
            self.payload = payload

        def tobytes(self, image_format):
            assert image_format == "png"
            return self.payload

    class FakePage:
        def __init__(self, payload):
            self.payload = payload

        def get_pixmap(self, matrix):
            return FakePixmap(self.payload)

    class FakeDocument(list):
        closed = False

        def close(self):
            self.closed = True

    document = FakeDocument([FakePage(b"page-1"), FakePage(b"page-2")])
    fake_fitz = SimpleNamespace(
        open=lambda **kwargs: document,
        Matrix=lambda zoom, zoom_y: (zoom, zoom_y),
    )
    monkeypatch.setitem(sys.modules, "fitz", fake_fitz)

    assert engine.pdf_pages_to_images(b"%PDF-test", max_pages=2) == [b"page-1", b"page-2"]
    assert document.closed is True
