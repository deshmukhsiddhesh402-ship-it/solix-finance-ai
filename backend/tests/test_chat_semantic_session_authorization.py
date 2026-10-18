"""Regression tests for semantic chat document session access controls."""
import time

import pytest
from fastapi import HTTPException

from app.routers import chat


SESSION_ID = "55555555-5555-4555-8555-555555555555"
ORG_ID = "6f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"
OTHER_ORG_ID = "7f1b7d5d-2c0a-4b9f-9a6d-7a0b5d9b1c22"
USER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_USER_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def semantic_session(monkeypatch):
    monkeypatch.setattr(chat, "_TFIDF_SESSIONS", {})
    monkeypatch.setattr(
        chat,
        "_SEMANTIC_SESSIONS",
        {
            SESSION_ID: {
                "filename": "sensitive-report.pdf",
                "org_id": ORG_ID,
                "user_id": USER_ID,
                "created_at": time.time(),
            }
        },
    )


def test_semantic_chat_session_rejects_cross_user_access(semantic_session):
    with pytest.raises(HTTPException) as exc:
        chat.ask_question(
            chat.AskRequest(session_id=SESSION_ID, question="Summarize the report"),
            org_id=ORG_ID,
            db=None,
            user_id=OTHER_USER_ID,
        )

    assert exc.value.status_code == 403


def test_semantic_chat_session_rejects_cross_organization_access(semantic_session):
    with pytest.raises(HTTPException) as exc:
        chat.ask_question(
            chat.AskRequest(session_id=SESSION_ID, question="Summarize the report"),
            org_id=OTHER_ORG_ID,
            db=None,
            user_id=USER_ID,
        )

    assert exc.value.status_code == 403
