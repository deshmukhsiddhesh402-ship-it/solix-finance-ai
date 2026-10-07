"""
Module 7: AI Chat / RAG — retrieval engine.

NOTE ON DESIGN: Claude does not offer a public embeddings endpoint.
Anthropic's own docs recommend a dedicated embeddings provider (e.g. Voyage
AI) for production RAG, and the schema already has a pgvector column ready
for that (`document_chunks.embedding`). To keep this module fully working
*today*, without requiring an extra API key, this file implements classic
TF-IDF + cosine similarity retrieval in pure Python — it's a real, correct,
testable retrieval algorithm, not a stub. Swapping in real embeddings later
means: replace `build_index`/`retrieve` calls with an embedding-API call
and a pgvector similarity query — the router code around it barely changes.
"""
import math
import re
from collections import Counter


_WORD_RE = re.compile(r"[a-zA-Z0-9₹%]+")
MAX_RAG_CHUNKS = 10_000
MAX_RAG_QUERY_CHARS = 4_000
MAX_RAG_TOP_K = 10
MAX_RAG_CHUNK_CHARS = 20_000
MAX_RAG_TOTAL_CHARS = 5_000_000


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def build_index(chunks: list[str]) -> dict:
    """Build TF-IDF vectors for a list of text chunks."""
    if not isinstance(chunks, list) or len(chunks) > MAX_RAG_CHUNKS:
        raise ValueError("RAG index exceeds the supported chunk limit.")
    if any(not isinstance(chunk, str) or not chunk for chunk in chunks):
        raise ValueError("RAG chunks must be non-empty strings.")
    if any(len(chunk) > MAX_RAG_CHUNK_CHARS for chunk in chunks):
        raise ValueError("A RAG chunk exceeds the supported size limit.")
    if sum(len(chunk) for chunk in chunks) > MAX_RAG_TOTAL_CHARS:
        raise ValueError("RAG input exceeds the supported total text limit.")
    tokenized = [_tokenize(c) for c in chunks]
    doc_count = len(tokenized)

    # Document frequency: in how many chunks does each term appear?
    df = Counter()
    for tokens in tokenized:
        for term in set(tokens):
            df[term] += 1

    idf = {term: math.log((1 + doc_count) / (1 + freq)) + 1 for term, freq in df.items()}

    vectors = []
    for tokens in tokenized:
        tf = Counter(tokens)
        length = len(tokens) or 1
        vec = {term: (count / length) * idf.get(term, 0.0) for term, count in tf.items()}
        vectors.append(vec)

    return {"chunks": chunks, "vectors": vectors, "idf": idf}


def _cosine_similarity(vec_a: dict, vec_b: dict) -> float:
    common_terms = set(vec_a) & set(vec_b)
    dot = sum(vec_a[t] * vec_b[t] for t in common_terms)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve(query: str, index: dict, top_k: int = 4) -> list[dict]:
    """Return the top_k most relevant chunks for a query, with scores."""
    if not isinstance(query, str) or len(query) > MAX_RAG_QUERY_CHARS:
        raise ValueError("RAG query exceeds the supported length limit.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1 or top_k > MAX_RAG_TOP_K:
        raise ValueError("top_k must be between 1 and 10.")
    tokens = _tokenize(query)
    tf = Counter(tokens)
    length = len(tokens) or 1
    query_vec = {term: (count / length) * index["idf"].get(term, 0.0) for term, count in tf.items()}

    scored = [
        {"chunk": chunk, "score": round(_cosine_similarity(query_vec, vec), 4)}
        for chunk, vec in zip(index["chunks"], index["vectors"])
    ]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [s for s in scored[:top_k] if s["score"] > 0]


# ---------------------------------------------------------------------------
# Semantic (embeddings + pgvector) retrieval — used when VOYAGE_API_KEY is
# configured. Requires a live Postgres connection with the pgvector
# extension enabled (see database/schema.sql).
# ---------------------------------------------------------------------------
def _validate_query_embedding(query_embedding: list[float]) -> None:
    from app.services.embedding_service import EMBEDDING_DIMENSIONS

    if not isinstance(query_embedding, list) or len(query_embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError("RAG query embedding has an unexpected dimension.")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in query_embedding
    ):
        raise ValueError("RAG query embedding contains invalid values.")


def semantic_retrieve(db, document_id, query_embedding: list[float], top_k: int = 4) -> list[dict]:
    """Cosine-similarity search over a document's chunks using pgvector.
    `db` is a SQLAlchemy Session (see app.core.db.get_db).
    """
    from app.models.document import DocumentChunk  # local import: avoids a hard DB dependency for TF-IDF-only setups

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1 or top_k > MAX_RAG_TOP_K:
        raise ValueError("top_k must be between 1 and 10.")
    _validate_query_embedding(query_embedding)

    rows = (
        db.query(DocumentChunk, DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"))
        .filter(DocumentChunk.document_id == document_id)
        .order_by("distance")
        .limit(top_k)
        .all()
    )
    return [
        {"chunk": chunk.chunk_text, "score": round(1 - distance, 4), "chunk_id": str(chunk.id)}
        for chunk, distance in rows
    ]
