"""Regression tests for provider-safe semantic document embedding batches."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers import chat


def test_semantic_embeddings_are_batched_at_provider_limit(monkeypatch):
    calls = []

    def fake_get_embeddings(batch, input_type):
        calls.append((list(batch), input_type))
        return [[float(len(text))] for text in batch]

    monkeypatch.setattr(chat, "get_embeddings", fake_get_embeddings)
    chunks = [f"document chunk {i}" for i in range(chat.MAX_EMBEDDING_BATCH + 1)]

    embedded_chunks, vectors = chat._embed_document_chunks(chunks)

    assert embedded_chunks == chunks
    assert [len(batch) for batch, _ in calls] == [chat.MAX_EMBEDDING_BATCH, 1]
    assert all(kind == "document" for _, kind in calls)
    assert len(vectors) == len(chunks)
    assert vectors == [[float(len(chunk))] for chunk in chunks]


def test_embedding_chunks_are_split_without_losing_words():
    chunks = ["alpha " * 1000]

    split = chat._split_embedding_chunks(chunks, max_chars=128)

    assert len(split) > 1
    assert all(len(part) <= 128 for part in split)
    assert " ".join(split).split() == chunks[0].split()


def test_embedding_chunk_rejects_single_word_over_provider_limit():
    with pytest.raises(ValueError, match="token exceeds"):
        chat._split_embedding_chunks(["x" * 129], max_chars=128)


@pytest.mark.parametrize("max_chars", [0, -1, True, 1.5])
def test_embedding_chunk_rejects_invalid_provider_limits(max_chars):
    with pytest.raises(ValueError, match="positive integer"):
        chat._split_embedding_chunks(["small text"], max_chars=max_chars)


def test_semantic_embedding_checks_provider_result_count(monkeypatch):
    monkeypatch.setattr(chat, "get_embeddings", lambda batch, input_type: [])
    with pytest.raises(RuntimeError, match="unexpected result count"):
        chat._embed_document_chunks(["one small chunk"])


def test_semantic_embedding_hides_provider_exception_details(monkeypatch):
    def fail_provider(*_args, **_kwargs):
        raise RuntimeError("provider credential detail")

    monkeypatch.setattr(chat, "get_embeddings", fail_provider)

    with pytest.raises(RuntimeError, match="Semantic embedding provider request failed") as exc:
        chat._embed_document_chunks(["one small chunk"])

    assert "provider credential detail" not in str(exc.value)


def test_chat_upload_maps_semantic_embedding_failure_to_generic_502(monkeypatch):
    upload = SimpleNamespace(filename="ledger.txt", read=AsyncMock(return_value=b"document"))
    monkeypatch.setattr(chat, "extract_text", lambda *_args: "ledger context")
    monkeypatch.setattr(chat, "chunk_text", lambda _text: ["ledger context"])
    monkeypatch.setattr(chat, "reserve_ai_usage", lambda *_args: None)
    monkeypatch.setattr(chat, "embeddings_available", lambda: True)

    def fail_embedding(_chunks):
        raise RuntimeError("provider credential detail")

    monkeypatch.setattr(chat, "_embed_document_chunks", fail_embedding)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            chat.upload_document(
                file=upload,
                org_id=str(uuid4()),
                db=object(),
                user_id=str(uuid4()),
            )
        )

    assert exc.value.status_code == 502
    assert exc.value.detail == "Semantic embedding provider request failed."
    assert "provider credential detail" not in exc.value.detail
