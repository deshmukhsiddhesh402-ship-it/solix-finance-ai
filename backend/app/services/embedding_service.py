"""
Module 7 upgrade: real semantic embeddings for RAG.

WHY VOYAGE AI: Claude does not have a public embeddings endpoint. Anthropic's
own docs recommend Voyage AI as the embeddings provider to pair with Claude
for RAG (https://docs.claude.com — search "embeddings"). This wrapper is
intentionally provider-agnostic in shape (get_embeddings(texts) -> list of
vectors) so swapping providers later only touches this one file.

GRACEFUL DEGRADATION: if VOYAGE_API_KEY isn't set, `embeddings_available()`
returns False and the RAG router falls back to the TF-IDF retrieval already
built in rag_engine.py — so the app keeps working out of the box without
requiring a second API key, and upgrades automatically once one is added.
"""
import math
import voyageai
from app.core.config import settings

_client = voyageai.Client(api_key=settings.VOYAGE_API_KEY) if settings.VOYAGE_API_KEY else None

EMBEDDING_MODEL = "voyage-3"
EMBEDDING_DIMENSIONS = 1024  # voyage-3 default output dimension
MAX_EMBEDDING_BATCH = 128
MAX_EMBEDDING_TEXTS_CHARS = 5_000_000
MAX_EMBEDDING_TEXT_CHARS = 4_000


def embeddings_available() -> bool:
    return _client is not None


def get_embeddings(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed a batch of texts. input_type is 'document' when indexing chunks,
    'query' when embedding a user's question — Voyage tunes the embedding
    differently for each, which measurably improves retrieval quality.
    """
    if not _client:
        raise RuntimeError("VOYAGE_API_KEY is not configured — embeddings unavailable.")
    if input_type not in {"document", "query"}:
        raise ValueError("input_type must be 'document' or 'query'.")
    if not isinstance(texts, list) or len(texts) < 1 or len(texts) > MAX_EMBEDDING_BATCH:
        raise ValueError("Embedding batch size must be between 1 and 128.")
    if any(not isinstance(text, str) or not text for text in texts):
        raise ValueError("Embedding inputs must be non-empty strings.")
    if any(len(text) > MAX_EMBEDDING_TEXT_CHARS for text in texts):
        raise ValueError("An embedding input exceeds the supported text length.")
    if sum(len(text) for text in texts) > MAX_EMBEDDING_TEXTS_CHARS:
        raise ValueError("Embedding batch exceeds the supported total text length.")
    result = _client.embed(texts, model=EMBEDDING_MODEL, input_type=input_type)
    embeddings = result.embeddings
    if len(embeddings) != len(texts):
        raise RuntimeError("Embedding provider returned an unexpected result count.")
    if any(len(vector) != EMBEDDING_DIMENSIONS for vector in embeddings):
        raise RuntimeError("Embedding provider returned an unexpected vector dimension.")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for vector in embeddings
        for value in vector
    ):
        raise RuntimeError("Embedding provider returned a non-finite or invalid vector value.")
    return embeddings


def get_query_embedding(query: str) -> list[float]:
    return get_embeddings([query], input_type="query")[0]
