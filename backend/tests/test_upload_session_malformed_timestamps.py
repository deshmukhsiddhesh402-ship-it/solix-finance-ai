"""Regression tests for malformed timestamps in in-memory upload sessions."""

from app.routers import excel_automation as excel
from app.routers import invoice_ocr as ocr


MALFORMED_SESSIONS = {
    "missing-timestamp": {},
    "string-timestamp": {"created_at": "not-a-timestamp"},
    "boolean-timestamp": {"created_at": True},
    "nan-timestamp": {"created_at": float("nan")},
    "infinite-timestamp": {"created_at": float("inf")},
    "oversized-integer-timestamp": {"created_at": 10**1000},
    "non-dictionary-session": None,
}


def test_excel_session_purger_removes_malformed_timestamps(monkeypatch):
    sessions = {
        **MALFORMED_SESSIONS,
        "valid-session": {"created_at": 950.0},
    }
    monkeypatch.setattr(excel, "_CLEANED_FILES", sessions)
    monkeypatch.setattr(excel, "CLEANED_SESSION_TTL_SECONDS", 100)

    excel._purge_expired_cleaned_sessions(now=1000.0)

    assert set(sessions) == {"valid-session"}


def test_ocr_session_purger_removes_malformed_timestamps(monkeypatch):
    sessions = {
        **MALFORMED_SESSIONS,
        "valid-session": {"created_at": 950.0},
    }
    monkeypatch.setattr(ocr, "_EXTRACTED_INVOICES", sessions)
    monkeypatch.setattr(ocr, "OCR_SESSION_TTL_SECONDS", 100)

    ocr._purge_expired_sessions(now=1000.0)

    assert set(sessions) == {"valid-session"}
