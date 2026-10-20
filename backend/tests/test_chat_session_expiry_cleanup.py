from app.routers import chat


def test_purge_expired_chat_sessions_removes_expired_entries_from_both_stores(monkeypatch):
    tfidf_sessions = {
        "expired-keyword": {"created_at": 100.0},
        "active-keyword": {"created_at": 200.0},
    }
    semantic_sessions = {
        "expired-semantic": {"created_at": 99.0},
        "active-semantic": {"created_at": 250.0},
    }
    monkeypatch.setattr(chat, "_TFIDF_SESSIONS", tfidf_sessions)
    monkeypatch.setattr(chat, "_SEMANTIC_SESSIONS", semantic_sessions)
    monkeypatch.setattr(chat, "CHAT_SESSION_TTL_SECONDS", 100)

    chat._purge_expired_chat_sessions(now=200.0)

    assert set(tfidf_sessions) == {"active-keyword"}
    assert set(semantic_sessions) == {"active-semantic"}


def test_purge_expired_chat_sessions_keeps_session_before_ttl_boundary(monkeypatch):
    tfidf_sessions = {"still-valid": {"created_at": 100.001}}
    semantic_sessions = {}
    monkeypatch.setattr(chat, "_TFIDF_SESSIONS", tfidf_sessions)
    monkeypatch.setattr(chat, "_SEMANTIC_SESSIONS", semantic_sessions)
    monkeypatch.setattr(chat, "CHAT_SESSION_TTL_SECONDS", 100)

    chat._purge_expired_chat_sessions(now=200.0)

    assert "still-valid" in tfidf_sessions



def test_purge_expired_chat_sessions_removes_entries_without_valid_timestamps(monkeypatch):
    tfidf_sessions = {
        "missing-timestamp": {"filename": "legacy.txt"},
        "non-finite-timestamp": {"created_at": float("nan")},
        "valid-session": {"created_at": 150.0},
    }
    semantic_sessions = {
        "invalid-timestamp": {"created_at": "not-a-timestamp"},
        "non-dict-session": "malformed-entry",
    }
    monkeypatch.setattr(chat, "_TFIDF_SESSIONS", tfidf_sessions)
    monkeypatch.setattr(chat, "_SEMANTIC_SESSIONS", semantic_sessions)
    monkeypatch.setattr(chat, "CHAT_SESSION_TTL_SECONDS", 100)

    chat._purge_expired_chat_sessions(now=200.0)

    assert set(tfidf_sessions) == {"valid-session"}
    assert semantic_sessions == {}


def test_store_chat_session_discards_malformed_entries_before_eviction(monkeypatch):
    tfidf_sessions = {
        "malformed-timestamp": {"created_at": "not-a-timestamp"},
        "malformed-entry": "not-a-session-dict",
        "oldest-valid": {"created_at": 100.0},
        "newest-valid": {"created_at": 200.0},
    }
    semantic_sessions = {}
    monkeypatch.setattr(chat, "_TFIDF_SESSIONS", tfidf_sessions)
    monkeypatch.setattr(chat, "_SEMANTIC_SESSIONS", semantic_sessions)
    monkeypatch.setattr(chat, "MAX_CHAT_SESSIONS", 3)
    monkeypatch.setattr(chat, "_purge_expired_chat_sessions", lambda: None)

    chat._store_chat_session(chat._TFIDF_SESSIONS, "new-session", {"created_at": 300.0})

    assert "malformed-timestamp" not in tfidf_sessions
    assert "malformed-entry" not in tfidf_sessions
    assert set(tfidf_sessions) == {"oldest-valid", "newest-valid", "new-session"}


def test_read_upload_limited_rejects_oversized_file_without_unbounded_read():
    import asyncio
    from fastapi import HTTPException

    class FakeUpload:
        requested_size = None

        async def read(self, size=-1):
            self.requested_size = size
            return b"x" * size

    upload = FakeUpload()
    try:
        asyncio.run(chat._read_upload_limited(upload))
    except HTTPException as exc:
        assert exc.status_code == 413
    else:
        raise AssertionError("Oversized upload should be rejected.")

    assert upload.requested_size == chat.MAX_UPLOAD_BYTES + 1
