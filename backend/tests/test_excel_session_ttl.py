import app.routers.excel_automation as excel


def test_cleaned_session_without_creation_timestamp_is_purged(monkeypatch):
    excel._CLEANED_FILES.clear()
    excel._CLEANED_FILES["missing-created-at"] = {}
    monkeypatch.setattr(excel, "CLEANED_SESSION_TTL_SECONDS", 30)
    excel._purge_expired_cleaned_sessions(now=1000.0)
    assert "missing-created-at" not in excel._CLEANED_FILES


def test_cleaned_session_younger_than_ttl_is_retained(monkeypatch):
    excel._CLEANED_FILES.clear()
    excel._CLEANED_FILES["fresh"] = {"created_at": 980.0}
    monkeypatch.setattr(excel, "CLEANED_SESSION_TTL_SECONDS", 30)
    excel._purge_expired_cleaned_sessions(now=1000.0)
    assert "fresh" in excel._CLEANED_FILES
    excel._CLEANED_FILES.clear()
