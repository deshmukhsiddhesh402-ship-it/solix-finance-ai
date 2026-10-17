import asyncio
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException

from app.routers.excel_automation import (
    MAX_ROWS,
    MAX_UPLOAD_BYTES,
    _read_bounded_upload,
    _read_upload_to_df,
)


def test_excel_upload_read_is_limited_to_maximum_plus_one_byte():
    upload = type("Upload", (), {})()
    upload.read = AsyncMock(return_value=b"x" * (MAX_UPLOAD_BYTES + 1))

    data = asyncio.run(_read_bounded_upload(upload))

    upload.read.assert_awaited_once_with(MAX_UPLOAD_BYTES + 1)
    assert len(data) == MAX_UPLOAD_BYTES + 1


def test_excel_upload_read_uses_configured_limit():
    upload = type("Upload", (), {})()
    upload.read = AsyncMock(return_value=b"small file")

    data = asyncio.run(_read_bounded_upload(upload, max_bytes=128))

    upload.read.assert_awaited_once_with(129)
    assert data == b"small file"


def test_xlsx_parser_caps_rows_before_dataframe_validation():
    oversized = pd.DataFrame({"value": range(MAX_ROWS + 1)})
    with patch("app.routers.excel_automation._validate_excel_archive") as validate_archive, patch(
        "app.routers.excel_automation.pd.read_excel", return_value=oversized
    ) as read_excel:
        with pytest.raises(HTTPException) as exc:
            _read_upload_to_df("ledger.xlsx", b"fake-xlsx")

    assert exc.value.status_code == 413
    validate_archive.assert_called_once()
    assert read_excel.call_args.kwargs["nrows"] == MAX_ROWS + 1
