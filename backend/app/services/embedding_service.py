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
import voyageai
from app.core.config import settings

_client = voyageai.Client(api_key=settings.VOYAGE_API_KEY) if settings.VOYAGE_API_KEY else None

EMBEDDING_MODEL = "voyage-3"
EMBEDDING_DIMENSIONS = 1024  # voyage-3 default output dimension


def embeddings_available() -> bool:
    return _client is not None


def get_embeddings(texts: list[str], input_type: str = "document") -> list[list[float]]:
    """Embed a batch of texts. input_type is 'document' when indexing chunks,
    'query' when embedding a user's question — Voyage tunes the embedding
    differently for each, which measurably improves retrieval quality.
    """
    if not _client:
        raise RuntimeError("VOYAGE_API_KEY is not configured — embeddings unavailable.")
    result = _client.embed(texts, model=EMBEDDING_MODEL, input_type=input_type)
    return result.embeddings


def get_query_embedding(query: str) -> list[float]:
    return get_embeddings([query], input_type="query")[0]
