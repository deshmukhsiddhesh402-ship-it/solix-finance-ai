"""
Module 7: AI Chat — document upload + RAG-grounded question answering.

RETRIEVAL MODE: automatically picks the best available option.
  - If VOYAGE_API_KEY is set: real semantic embeddings, persisted to Postgres
    via pgvector, with proper cosine-similarity search. This is the
    production path.
  - If not: falls back to the in-memory TF-IDF retrieval from rag_engine.py,
    so the module still works fully offline / without a second API key.
Every answer returns source citations either way, including the source
document's filename — not just an anonymous excerpt.
"""
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.document_engine import extract_text, chunk_text
from app.services.rag_engine import build_index, retrieve, semantic_retrieve
from app.services.embedding_service import embeddings_available, get_embeddings, get_query_embedding
from app.services.claude_service import ask_claude, rag_chat_prompt
from app.core.db import get_db

router = APIRouter()

# Fallback (keyword/TF-IDF) session store — same pattern as before.
# session_id -> {"filename": str, "index": dict}
_TFIDF_SESSIONS: dict[str, dict] = {}

# session_id -> filename, for semantic-mode sessions (the session_id doubles
# as the document's DB row id in that path).
_SEMANTIC_FILENAMES: dict[str, str] = {}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a PDF/Excel/Word/text file, extract + chunk + index it for RAG."""
    file_bytes = await file.read()
    try:
        text = extract_text(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    if not text.strip():
        raise HTTPException(422, detail="No extractable text found in this file (it may be a scanned/image PDF — see the OCR module for that case).")

    chunks = chunk_text(text)

    if embeddings_available():
        # --- Production path: real embeddings, persisted to pgvector ---
        from app.models.document import Document, DocumentChunk  # local import: only needed on this path

        vectors = get_embeddings(chunks, input_type="document")

        doc_row = Document(file_name=file.filename, file_type=file.filename.split(".")[-1])
        db.add(doc_row)
        db.flush()  # populate doc_row.id before creating children

        for chunk_text_, vector in zip(chunks, vectors):
            db.add(DocumentChunk(document_id=doc_row.id, chunk_text=chunk_text_, embedding=vector))
        db.commit()

        session_id = str(doc_row.id)
        _SEMANTIC_FILENAMES[session_id] = file.filename
        return {"session_id": session_id, "filename": file.filename, "chunk_count": len(chunks), "mode": "semantic"}

    # --- Fallback path: TF-IDF, in-memory ---
    index = build_index(chunks)
    session_id = str(uuid.uuid4())
    _TFIDF_SESSIONS[session_id] = {"filename": file.filename, "index": index}
    return {"session_id": session_id, "filename": file.filename, "chunk_count": len(chunks), "mode": "keyword"}


class AskRequest(BaseModel):
    session_id: str
    question: str
    top_k: int = 4


@router.post("/ask")
def ask_question(req: AskRequest, db: Session = Depends(get_db)):
    filename = None
    matches: list[dict] = []

    if req.session_id in _SEMANTIC_FILENAMES:
        filename = _SEMANTIC_FILENAMES[req.session_id]
        query_embedding = get_query_embedding(req.question)
        matches = semantic_retrieve(db, req.session_id, query_embedding, top_k=req.top_k)
    elif req.session_id in _TFIDF_SESSIONS:
        session = _TFIDF_SESSIONS[req.session_id]
        filename = session["filename"]
        matches = retrieve(req.question, session["index"], top_k=req.top_k)
    else:
        raise HTTPException(404, detail="Session not found. Upload a document first.")

    if not matches:
        return {"answer": "I couldn't find anything relevant to that question in the uploaded document.", "sources": []}

    retrieved_chunks = [m["chunk"] for m in matches]
    system, user_message = rag_chat_prompt(req.question, retrieved_chunks)
    answer = ask_claude(system, user_message, max_tokens=1000)

    return {
        "answer": answer,
        "sources": [
            {"document": filename, "excerpt": m["chunk"][:200], "relevance_score": m["score"]}
            for m in matches
        ],
    }
