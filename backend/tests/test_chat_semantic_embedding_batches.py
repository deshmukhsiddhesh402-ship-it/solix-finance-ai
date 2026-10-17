import pytest

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


def test_embedding_chunks_are_split_without_losing_text():
    chunks = ["alpha " * 1000]

    split = chat._split_embedding_chunks(chunks, max_chars=128)

    assert len(split) > 1
    assert all(len(part) <= 128 for part in split)
    assert " ".join(split).split() == chunks[0].split()


def test_embedding_chunk_rejects_single_word_over_provider_limit():
    with pytest.raises(ValueError, match="token exceeds"):
        chat._split_embedding_chunks(["x" * 129], max_chars=128)


def test_semantic_embedding_checks_provider_result_count(monkeypatch):
    monkeypatch.setattr(chat, "get_embeddings", lambda batch, input_type: [])
    with pytest.raises(RuntimeError, match="unexpected result count"):
        chat._embed_document_chunks(["one small chunk"])
