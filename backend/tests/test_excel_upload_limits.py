import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.routers.excel_automation as excel


ORG_ID = "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"
USER_ID = "11111111-1111-4111-8111-111111111111"


def test_excel_upload_rejects_oversized_chunked_body():
    upload = SimpleNamespace(filename="records.csv")

    async def read(size=-1):
        assert size == excel.MAX_UPLOAD_BYTES + 1
        return b"x" * (excel.MAX_UPLOAD_BYTES + 1)

    upload.read = read
    with pytest.raises(HTTPException) as exc:
        asyncio.run(excel.auto_clean(upload, True, None, ORG_ID, USER_ID))
    assert exc.value.status_code == 413
