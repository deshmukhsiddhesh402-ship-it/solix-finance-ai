"""Regression tests for bounded invoice-upload reads."""
import asyncio
import os
import sys
import uuid

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.routers.invoice_ocr import MAX_INVOICE_BYTES, extract_invoice


class OversizedUpload:
    filename = "invoice.png"

    def __init__(self):
        self.requested_size = None

    async def read(self, size=-1):
        self.requested_size = size
        return b"x" * size


def test_ocr_rejects_oversized_upload_after_bounded_read():
    upload = OversizedUpload()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(extract_invoice(
            file=upload,
            org_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        ))

    assert exc.value.status_code == 413
    assert upload.requested_size == MAX_INVOICE_BYTES + 1
