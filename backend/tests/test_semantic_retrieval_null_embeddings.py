"""Regression tests for semantic retrieval with legacy NULL embeddings."""
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.embedding_service import EMBEDDING_DIMENSIONS
from app.services.rag_engine import semantic_retrieve


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.ordering = None
        self.limit_value = None

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def order_by(self, ordering):
        self.ordering = ordering
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def all(self):
        return self.rows


class _DB:
    def __init__(self, query):
        self.query_result = query
        self.selected = None

    def query(self, *selected):
        self.selected = selected
        return self.query_result


def test_semantic_retrieval_filters_null_embedding_rows_before_distance_ordering():
    chunk = SimpleNamespace(id=uuid4(), chunk_text="valid embedded text")
    query = _Query([(chunk, 0.25)])
    db = _DB(query)

    result = semantic_retrieve(db, uuid4(), [0.1] * EMBEDDING_DIMENSIONS, top_k=3)

    assert result == [{
        "chunk": "valid embedded text",
        "score": 0.75,
        "chunk_id": str(chunk.id),
    }]
    assert len(query.filters) == 2
    assert "document_id" in str(query.filters[0])
    assert "embedding IS NOT NULL" in str(query.filters[1])
    assert query.ordering == "distance"
    assert query.limit_value == 3


def test_semantic_retrieval_returns_empty_when_no_non_null_vectors_match():
    query = _Query([])
    db = _DB(query)

    result = semantic_retrieve(db, uuid4(), [0.1] * EMBEDDING_DIMENSIONS)

    assert result == []
    assert len(query.filters) == 2
