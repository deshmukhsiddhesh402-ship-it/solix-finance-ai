"""Regression tests for aggregate row limits on Excel session merges."""
import sys
from pathlib import Path
import time

import pandas as pd
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import excel_automation


def test_excel_merge_rejects_aggregate_rows_over_limit(monkeypatch):
    org_id = "10000000-0000-4000-8000-000000000001"
    user_id = "20000000-0000-4000-8000-000000000002"
    session_ids = [
        "a0000000-0000-4000-8000-000000000001",
        "a0000000-0000-4000-8000-000000000002",
    ]
    for session_id in session_ids:
        monkeypatch.setitem(
            excel_automation._CLEANED_FILES,
            session_id,
            {
                "df": pd.DataFrame({"amount": [10, 20]}),
                "org_id": org_id,
                "user_id": user_id,
                "created_at": time.time(),
            },
        )
    monkeypatch.setattr(excel_automation, "MAX_ROWS", 3)

    with pytest.raises(HTTPException) as exc:
        excel_automation.merge_cleaned_sessions(
            excel_automation.MergeRequest(session_ids=session_ids),
            org_id=org_id,
            user_id=user_id,
        )

    assert exc.value.status_code == 413
    assert "row limit" in exc.value.detail
