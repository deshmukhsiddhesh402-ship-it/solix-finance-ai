"""Regression tests for document-upload embedding failures."""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException


class FakeUpload:
    filename = "ledger.txt"

    async def read(self):
        return b"ledger content"


class FakeDB:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    def flush(self):
        raise AssertionError("Database writes must not start before embeddings succeed.")


def _run_upload(monkeypatch, provider):
    from app.routers import chat

    monkeypatch.setattr(chat, "extract_text", lambda *_args: "Cash received 100")
    monkeypatch.setattr(chat, "chunk_text", lambda _text: ["Cash received 100"])
    monkeypatch.setattr(chat, "embeddings_available", lambda: True)
    monkeypatch.setattr(chat, "get_embeddings", provider)
    db = FakeDB()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            chat.upload_document(
                file=FakeUpload(),
                org_id=str(uuid4()),
                db=db,
                user_id=str(uuid4()),
            )
        )
    return exc.value, db


def test_document_upload_maps_embedding_provider_outage_to_generic_502(monkeypatch):
    def fail_provider(*_args, **_kwargs):
        raise RuntimeError("provider credential detail")

    error, db = _run_upload(monkeypatch, fail_provider)

    assert error.status_code == 502
    assert error.detail == "Document embedding provider request failed."
    assert "credential" not in error.detail
    assert db.added == []


def test_document_upload_maps_invalid_embedding_payload_to_422(monkeypatch):
    def reject_input(*_args, **_kwargs):
        raise ValueError("provider input limit detail")

    error, db = _run_upload(monkeypatch, reject_input)

    assert error.status_code == 422
    assert error.detail == "Document text exceeds supported embedding input limits."
    assert db.added == []
