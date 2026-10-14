"""Regression tests for bounded invoice upload reads."""
import asyncio
import uuid

import pytest
from fastapi import HTTPException

from app.routers import invoice_ocr


class OversizedUpload:
    filename = "invoice.png"

    def __init__(self):
        self.requested_size = None

    async def read(self, size=-1):
        self.requested_size = size
        return b"x" * size


def test_oversized_invoice_is_rejected_after_bounded_read():
    upload = OversizedUpload()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            invoice_ocr.extract_invoice(
                file=upload,
                org_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
            )
        )

    assert exc_info.value.status_code == 413
    assert upload.requested_size == invoice_ocr.MAX_INVOICE_BYTES + 1
