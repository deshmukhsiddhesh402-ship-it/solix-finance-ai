"""Regression tests for safe AI chat provider failures and responses."""

import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import chat


def _tfidf_session(monkeypatch):
    session_id = str(uuid4())
    org_id = str(uuid4())
    user_id = str(uuid4())
    monkeypatch.setitem(
        chat._TFIDF_SESSIONS,
        session_id,
        {
            "filename": "ledger.txt",
            "index": object(),
            "org_id": org_id,
            "user_id": user_id,
            "created_at": time.time(),
        },
    )
    monkeypatch.setattr(chat, "retrieve", lambda *_args, **_kwargs: [{"chunk": "ledger context", "score": 0.9}])
    return session_id, org_id, user_id


def test_chat_maps_claude_provider_exception_to_generic_502(monkeypatch):
    session_id, org_id, user_id = _tfidf_session(monkeypatch)

    def fail_provider(*_args, **_kwargs):
        raise RuntimeError("provider secret detail")

    monkeypatch.setattr(chat, "ask_claude", fail_provider)

    with pytest.raises(HTTPException) as exc:
        chat.ask_question(
            chat.AskRequest(session_id=session_id, question="What is the balance?"),
            org_id=org_id,
            db=object(),
            user_id=user_id,
        )

    assert exc.value.status_code == 502
    assert exc.value.detail == "AI chat provider request failed."
    assert "provider secret detail" not in exc.value.detail


@pytest.mark.parametrize("response", ["", "   ", None, {"answer": "unexpected"}])
def test_chat_rejects_blank_or_non_text_provider_answers(monkeypatch, response):
    session_id, org_id, user_id = _tfidf_session(monkeypatch)
    monkeypatch.setattr(chat, "ask_claude", lambda *_args, **_kwargs: response)

    with pytest.raises(HTTPException) as exc:
        chat.ask_question(
            chat.AskRequest(session_id=session_id, question="What is the balance?"),
            org_id=org_id,
            db=object(),
            user_id=user_id,
        )

    assert exc.value.status_code == 502
    assert exc.value.detail == "AI chat provider returned an invalid response."


def test_chat_maps_semantic_embedding_provider_failure_to_generic_502(monkeypatch):
    session_id = str(uuid4())
    org_id = str(uuid4())
    user_id = str(uuid4())
    doc_id = uuid4()
    monkeypatch.setitem(
        chat._SEMANTIC_SESSIONS,
        session_id,
        {
            "filename": "ledger.pdf",
            "org_id": org_id,
            "user_id": user_id,
            "created_at": time.time(),
        },
    )

    class FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return SimpleNamespace(id=doc_id, org_id=uuid4())

    class FakeDB:
        def query(self, _model):
            return FakeQuery()

    def fail_embedding(_question):
        raise RuntimeError("embedding provider detail")

    monkeypatch.setattr(chat, "get_query_embedding", fail_embedding)

    with pytest.raises(HTTPException) as exc:
        chat.ask_question(
            chat.AskRequest(session_id=session_id, question="What is the balance?"),
            org_id=org_id,
            db=FakeDB(),
            user_id=user_id,
        )

    assert exc.value.status_code == 502
    assert exc.value.detail == "Semantic search provider request failed."
    assert "embedding provider detail" not in exc.value.detail
