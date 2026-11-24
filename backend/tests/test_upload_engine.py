import asyncio
import pytest

from app.services.upload_engine import UploadTooLargeError, read_upload_limited


class FakeUpload:
    def __init__(self, payload: bytes):
        self.payload = payload
        self.requested_size = None

    async def read(self, size: int = -1) -> bytes:
        self.requested_size = size
        return self.payload[:size]


def test_bounded_reader_requests_only_limit_plus_one_bytes():
    upload = FakeUpload(b"x" * 100)
    result = asyncio.run(read_upload_limited(upload, 10))
    assert result == b"x" * 10
    assert upload.requested_size == 11


def test_bounded_reader_rejects_oversized_chunked_upload():
    upload = FakeUpload(b"x" * 11)
    with pytest.raises(UploadTooLargeError):
        asyncio.run(read_upload_limited(upload, 10))
    assert upload.requested_size == 11


def test_bounded_reader_accepts_exact_limit():
    upload = FakeUpload(b"x" * 10)
    assert asyncio.run(read_upload_limited(upload, 10)) == b"x" * 10


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "10"])
def test_bounded_reader_rejects_invalid_limits(limit):
    with pytest.raises(ValueError, match="max_bytes"):
        asyncio.run(read_upload_limited(FakeUpload(b""), limit))
