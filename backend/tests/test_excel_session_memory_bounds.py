"""Regression tests for bounded in-memory cleaned spreadsheet sessions."""
import sys
from pathlib import Path
import time

import pandas as pd
import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import excel_automation


def test_cleaned_session_store_rejects_per_session_memory_over_limit(monkeypatch):
    monkeypatch.setattr(excel_automation, "_CLEANED_FILES", {})
    monkeypatch.setattr(excel_automation, "MAX_CLEANED_SESSION_BYTES", 1)

    with pytest.raises(HTTPException) as exc:
        excel_automation._store_cleaned_session(
            "session-large",
            {"df": pd.DataFrame({"description": ["a" * 100]}), "created_at": time.time()},
        )

    assert exc.value.status_code == 413
    assert not excel_automation._CLEANED_FILES


def test_cleaned_session_store_evicts_oldest_to_respect_total_memory_budget(monkeypatch):
    monkeypatch.setattr(excel_automation, "_CLEANED_FILES", {})
    monkeypatch.setattr(excel_automation, "MAX_CLEANED_SESSION_BYTES", 1024 * 1024)
    monkeypatch.setattr(excel_automation, "MAX_CLEANED_SESSIONS", 10)
    sample = {"df": pd.DataFrame({"amount": [10, 20, 30]}), "created_at": 1}
    one_session_bytes = excel_automation._cleaned_session_memory_bytes(sample)
    monkeypatch.setattr(excel_automation, "MAX_CLEANED_CACHE_BYTES", one_session_bytes)

    excel_automation._store_cleaned_session("oldest", sample)
    excel_automation._store_cleaned_session(
        "newest",
        {"df": pd.DataFrame({"amount": [40, 50, 60]}), "created_at": time.time() + 1},
    )

    assert "oldest" not in excel_automation._CLEANED_FILES
    assert "newest" in excel_automation._CLEANED_FILES


def test_replacing_cached_session_does_not_evict_another_at_session_limit(monkeypatch):
    now = time.time()
    monkeypatch.setattr(
        excel_automation,
        "_CLEANED_FILES",
        {
            "oldest": {
                "df": pd.DataFrame({"amount": [10]}),
                "created_at": now,
            },
            "replace-me": {
                "df": pd.DataFrame({"amount": [20]}),
                "created_at": now + 1,
            },
        },
    )
    monkeypatch.setattr(excel_automation, "MAX_CLEANED_SESSIONS", 2)
    monkeypatch.setattr(excel_automation, "MAX_CLEANED_SESSION_BYTES", 1024 * 1024)
    monkeypatch.setattr(excel_automation, "MAX_CLEANED_CACHE_BYTES", 1024 * 1024)

    replacement = {
        "df": pd.DataFrame({"amount": [30]}),
        "created_at": now + 2,
    }
    excel_automation._store_cleaned_session("replace-me", replacement)

    assert "oldest" in excel_automation._CLEANED_FILES
    assert excel_automation._CLEANED_FILES["replace-me"] is replacement
    assert len(excel_automation._CLEANED_FILES) == 2
