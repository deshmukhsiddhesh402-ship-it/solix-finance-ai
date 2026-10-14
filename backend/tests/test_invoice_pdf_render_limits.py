"""Regression tests for bounded PDF rasterization resource use."""
import sys
from types import SimpleNamespace

import pytest

from app.services import invoice_ocr_engine


class FakePage:
    def __init__(self, width=612, height=792):
        self.rect = SimpleNamespace(width=width, height=height)
        self.rendered = False

    def get_pixmap(self, matrix):
        self.rendered = True
        return SimpleNamespace(tobytes=lambda fmt: b"png-data")


class FakeDocument:
    def __init__(self, pages):
        self.pages = pages
        self.closed = False

    def __iter__(self):
        return iter(self.pages)

    def close(self):
        self.closed = True


def install_fake_fitz(monkeypatch, document):
    monkeypatch.setitem(
        sys.modules,
        "fitz",
        SimpleNamespace(
            open=lambda **kwargs: document,
            Matrix=lambda x, y: (x, y),
        ),
    )


@pytest.mark.parametrize("dpi", [0, -1, 301, True])
def test_pdf_renderer_rejects_invalid_or_excessive_dpi(monkeypatch, dpi):
    document = FakeDocument([FakePage()])
    install_fake_fitz(monkeypatch, document)

    with pytest.raises(ValueError, match="DPI must be between"):
        invoice_ocr_engine.pdf_pages_to_images(b"%PDF-", dpi=dpi)

    assert document.closed is False


@pytest.mark.parametrize("max_pages", [0, -1, 21, True])
def test_pdf_renderer_rejects_invalid_or_excessive_page_count(monkeypatch, max_pages):
    document = FakeDocument([FakePage()])
    install_fake_fitz(monkeypatch, document)

    with pytest.raises(ValueError, match="max_pages must be between"):
        invoice_ocr_engine.pdf_pages_to_images(b"%PDF-", max_pages=max_pages)

    assert document.closed is False


def test_pdf_renderer_rejects_enormous_page_before_allocating_pixels(monkeypatch):
    page = FakePage(width=100_000, height=100_000)
    document = FakeDocument([page])
    install_fake_fitz(monkeypatch, document)

    with pytest.raises(ValueError, match="page dimensions exceed"):
        invoice_ocr_engine.pdf_pages_to_images(b"%PDF-", dpi=200)

    assert page.rendered is False
    assert document.closed is True


def test_pdf_renderer_closes_document_after_success(monkeypatch):
    page = FakePage()
    document = FakeDocument([page])
    install_fake_fitz(monkeypatch, document)

    images = invoice_ocr_engine.pdf_pages_to_images(b"%PDF-", dpi=200)

    assert images == [b"png-data"]
    assert page.rendered is True
    assert document.closed is True


def test_pdf_renderer_stops_iterating_at_max_pages(monkeypatch):
    class TrackingDocument(FakeDocument):
        def __init__(self, pages):
            super().__init__(pages)
            self.iterated = 0

        def __iter__(self):
            for page in self.pages:
                self.iterated += 1
                yield page

    document = TrackingDocument([FakePage() for _ in range(10)])
    install_fake_fitz(monkeypatch, document)
    images = invoice_ocr_engine.pdf_pages_to_images(b"%PDF-", max_pages=2)
    assert len(images) == 2
    assert document.iterated == 2
    assert document.closed is True
