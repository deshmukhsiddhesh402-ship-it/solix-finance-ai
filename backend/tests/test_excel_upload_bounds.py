import asyncio

import pytest
from fastapi import HTTPException

from app.routers.excel_automation import MAX_UPLOAD_BYTES, _read_bounded_upload


class FakeUpload:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.requested_size = None

    async def read(self, size: int = -1) -> bytes:
        self.requested_size = size
        return self.payload[:size]


def test_excel_upload_reads_only_through_one_byte_over_limit():
    upload = FakeUpload(b"x" * (MAX_UPLOAD_BYTES + 1))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(_read_bounded_upload(upload))

    assert exc.value.status_code == 413
    assert upload.requested_size == MAX_UPLOAD_BYTES + 1


def test_excel_upload_accepts_file_at_exact_limit():
    upload = FakeUpload(b"x" * MAX_UPLOAD_BYTES)

    result = asyncio.run(_read_bounded_upload(upload))

    assert len(result) == MAX_UPLOAD_BYTES
    assert upload.requested_size == MAX_UPLOAD_BYTES + 1
