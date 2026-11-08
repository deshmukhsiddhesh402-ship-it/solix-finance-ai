"""Regression tests for bounded AI chat document uploads."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import chat


def test_chat_upload_reader_reads_only_limit_plus_one_bytes():
    upload = SimpleNamespace(read=AsyncMock(return_value=b"x" * 6))

    data = asyncio.run(chat._read_bounded_upload(upload, max_bytes=5))

    upload.read.assert_awaited_once_with(6)
    assert data == b"x" * 6


def test_chat_upload_reader_accepts_payload_at_limit():
    upload = SimpleNamespace(read=AsyncMock(return_value=b"12345"))

    data = asyncio.run(chat._read_bounded_upload(upload, max_bytes=5))

    upload.read.assert_awaited_once_with(6)
    assert data == b"12345"


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_chat_upload_reader_rejects_invalid_limits_without_reading(limit):
    upload = SimpleNamespace(read=AsyncMock(return_value=b""))

    with pytest.raises(ValueError, match="positive integer"):
        asyncio.run(chat._read_bounded_upload(upload, max_bytes=limit))

    upload.read.assert_not_awaited()


def test_chat_upload_endpoint_rejects_oversized_file_before_parsing(monkeypatch):
    upload = SimpleNamespace(
        filename="oversized.txt",
        read=AsyncMock(return_value=b"x" * (chat.MAX_UPLOAD_BYTES + 1)),
    )
    parse = SimpleNamespace()
    monkeypatch.setattr(chat, "extract_text", lambda *_args: pytest.fail("oversized content must not be parsed"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            chat.upload_document(
                file=upload,
                org_id=str(uuid4()),
                db=object(),
                user_id=str(uuid4()),
            )
        )

    assert exc.value.status_code == 413
    assert exc.value.detail == "Uploaded document exceeds the 10 MB limit."
    upload.read.assert_awaited_once_with(chat.MAX_UPLOAD_BYTES + 1)
