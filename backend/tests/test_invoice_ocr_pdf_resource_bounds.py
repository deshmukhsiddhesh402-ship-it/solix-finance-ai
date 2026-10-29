"""Regression tests for PDF page rasterization resource bounds."""
import os
import sys
from types import SimpleNamespace

import fitz
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.invoice_ocr_engine import MAX_PDF_PAGE_PIXELS, pdf_pages_to_images


class HugePage:
    rect = SimpleNamespace(width=1_000_000, height=1_000_000)

    def get_pixmap(self, **kwargs):
        raise AssertionError("Oversized PDF page must be rejected before rasterization")


class FakeDocument:
    def __init__(self):
        self.closed = False

    def __iter__(self):
        return iter([HugePage()])

    def close(self):
        self.closed = True


def test_pdf_page_pixel_cap_rejects_huge_page_before_render(monkeypatch):
    document = FakeDocument()
    monkeypatch.setattr(fitz, "open", lambda **kwargs: document)

    with pytest.raises(ValueError, match="safe rasterization limit"):
        pdf_pages_to_images(b"%PDF-test", dpi=200, max_pages=1)

    assert document.closed is True
    assert MAX_PDF_PAGE_PIXELS == 25_000_000
