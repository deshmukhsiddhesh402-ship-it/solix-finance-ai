"""Module 7: AI Chat — tenant-scoped document upload + RAG."""
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.document_engine import extract_text, chunk_text
from app.services.rag_engine import build_index, retrieve, semantic_retrieve
from app.services.embedding_service import embeddings_available, get_embeddings, get_query_embedding
from app.services.claude_service import ask_claude, rag_chat_prompt
from app.core.db import get_db
from app.routers.enterprise import require_permission

router = APIRouter()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# session_id -> {filename, index, org_id}
_TFIDF_SESSIONS: dict[str, dict] = {}
# session_id -> {filename, org_id, user_id}
_SEMANTIC_SESSIONS: dict[str, dict] = {}


def _authorized_session_org(session_org_id: str, org_id: str) -> bool:
    return session_org_id == org_id


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(require_permission("chat", "create")),
):
    try:
        org_uuid = uuid.UUID(org_id)
        user_uuid = uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or user identifier.") from exc

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail="Uploaded document exceeds the 10 MB limit.")
    try:
        text = extract_text(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    if not text.strip():
        raise HTTPException(422, detail="No extractable text found in this file.")

    chunks = chunk_text(text)
    if embeddings_available():
        from app.models.document import Document, DocumentChunk
        vectors = get_embeddings(chunks, input_type="document")
        doc_row = Document(
            org_id=org_uuid, uploaded_by=user_uuid,
            file_name=file.filename, file_type=file.filename.split(".")[-1],
        )
        db.add(doc_row)
        db.flush()
        for chunk_text_, vector in zip(chunks, vectors):
            db.add(DocumentChunk(document_id=doc_row.id, chunk_text=chunk_text_, embedding=vector))
        db.commit()
        session_id = str(doc_row.id)
        _SEMANTIC_SESSIONS[session_id] = {
            "filename": file.filename, "org_id": str(org_uuid), "user_id": str(user_uuid),
        }
        return {"session_id": session_id, "filename": file.filename, "chunk_count": len(chunks), "mode": "semantic"}

    session_id = str(uuid.uuid4())
    _TFIDF_SESSIONS[session_id] = {
        "filename": file.filename, "index": build_index(chunks), "org_id": str(org_uuid),
        "user_id": str(user_uuid),
    }
    return {"session_id": session_id, "filename": file.filename, "chunk_count": len(chunks), "mode": "keyword"}


class AskRequest(BaseModel):
    session_id: str
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=4, ge=1, le=10)


@router.post("/ask")
def ask_question(
    req: AskRequest,
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("chat", "view")),
):
    filename = None
    matches: list[dict] = []

    if req.session_id in _SEMANTIC_SESSIONS:
        session = _SEMANTIC_SESSIONS[req.session_id]
        if not _authorized_session_org(session["org_id"], org_id):
            raise HTTPException(403, detail="Document does not belong to this organization.")
        if session["user_id"] != _user:
            raise HTTPException(403, detail="Document session does not belong to this user.")
        from app.models.document import Document
        try:
            doc_uuid = uuid.UUID(req.session_id)
            org_uuid = uuid.UUID(org_id)
        except (ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(400, detail="Invalid session or organization identifier.") from exc
        doc = db.query(Document).filter(Document.id == doc_uuid, Document.org_id == org_uuid).first()
        if not doc:
            raise HTTPException(404, detail="Document session not found.")
        filename = session["filename"]
        query_embedding = get_query_embedding(req.question)
        matches = semantic_retrieve(db, doc_uuid, query_embedding, top_k=req.top_k)
    elif req.session_id in _TFIDF_SESSIONS:
        session = _TFIDF_SESSIONS[req.session_id]
        if not _authorized_session_org(session["org_id"], org_id):
            raise HTTPException(403, detail="Document does not belong to this organization.")
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
