"""Regression tests for missing and oversized document upload filenames."""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeUpload:
    def __init__(self, filename):
        self.filename = filename
        self.read_called = False

    async def read(self):
        self.read_called = True
        raise AssertionError("Invalid filenames must be rejected before reading the upload.")


@pytest.mark.parametrize("filename", [None, "", "   "])
def test_chat_upload_rejects_missing_filename_before_read(filename):
    from app.routers.chat import upload_document

    upload = FakeUpload(filename)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_document(
                file=upload,
                org_id=str(uuid4()),
                db=None,
                user_id=str(uuid4()),
            )
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "A document filename is required."
    assert upload.read_called is False


def test_chat_upload_rejects_filename_longer_than_database_column():
    from app.routers.chat import upload_document

    upload = FakeUpload("a" * 256 + ".pdf")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            upload_document(
                file=upload,
                org_id=str(uuid4()),
                db=None,
                user_id=str(uuid4()),
            )
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Document filename cannot exceed 255 characters."
    assert upload.read_called is False
