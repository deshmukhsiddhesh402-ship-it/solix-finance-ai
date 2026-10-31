"""Regression tests for duplicate session references in Excel merges."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers.excel_automation import MergeRequest, merge_cleaned_sessions


def test_excel_merge_rejects_duplicate_session_ids_even_with_different_casing():
    session_id = "a0b1c2d3-e4f5-4678-9012-3456789abcde"
    request = MergeRequest(session_ids=[session_id, session_id.upper()])

    with pytest.raises(HTTPException) as exc:
        merge_cleaned_sessions(
            request,
            org_id="10000000-0000-4000-8000-000000000001",
            user_id="20000000-0000-4000-8000-000000000002",
        )

    assert exc.value.status_code == 422
    assert "Duplicate" in exc.value.detail
