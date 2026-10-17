import asyncio
from unittest.mock import AsyncMock

from app.routers.chat import MAX_UPLOAD_BYTES, _read_bounded_upload


def test_chat_upload_read_is_limited_to_maximum_plus_one_byte():
    upload = type("Upload", (), {})()
    upload.read = AsyncMock(return_value=b"x" * (MAX_UPLOAD_BYTES + 1))

    data = asyncio.run(_read_bounded_upload(upload))

    upload.read.assert_awaited_once_with(MAX_UPLOAD_BYTES + 1)
    assert len(data) == MAX_UPLOAD_BYTES + 1


def test_chat_upload_read_uses_configured_limit():
    upload = type("Upload", (), {})()
    upload.read = AsyncMock(return_value=b"small file")

    data = asyncio.run(_read_bounded_upload(upload, max_bytes=128))

    upload.read.assert_awaited_once_with(129)
    assert data == b"small file"
