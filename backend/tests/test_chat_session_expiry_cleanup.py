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
