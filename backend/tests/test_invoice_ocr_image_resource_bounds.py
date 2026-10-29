"""Regression tests for decoded image pixel limits."""
import os
import sys
import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.routers.invoice_ocr as ocr


class OversizedImage:
    size = (10_000, 10_000)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def verify(self):
        raise AssertionError("Oversized image must be rejected before verification")


def test_image_pixel_cap_rejects_oversized_dimensions(monkeypatch):
    monkeypatch.setattr(ocr.Image, "open", lambda payload: OversizedImage())

    with pytest.raises(HTTPException) as exc:
        ocr._validate_image_dimensions(b"image bytes")

    assert exc.value.status_code == 413
    assert ocr.MAX_IMAGE_PIXELS == 25_000_000
