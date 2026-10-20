"""Module 7: AI Chat — tenant-scoped document upload + RAG."""
import uuid
import time
import math
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
MAX_CHAT_SESSIONS = 1000
CHAT_SESSION_TTL_SECONDS = 30 * 60

# session_id -> {filename, index, org_id}
_TFIDF_SESSIONS: dict[str, dict] = {}
# session_id -> {filename, org_id, user_id}
_SEMANTIC_SESSIONS: dict[str, dict] = {}


def _valid_session_timestamp(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def _purge_expired_chat_sessions(now: float | None = None) -> None:
    current = time.time() if now is None else now
    for store in (_TFIDF_SESSIONS, _SEMANTIC_SESSIONS):
        expired = []
        for sid, session in store.items():
            # In-memory state can be malformed after unexpected writes or
            # legacy code paths; discard non-mapping entries without crashing.
            if not isinstance(session, dict):
                expired.append(sid)
                continue
            created_at = session.get("created_at")
            # Fail closed for malformed in-memory entries: sessions without a
            # valid timestamp must not bypass the TTL indefinitely.
            if (
                not _valid_session_timestamp(created_at)
                or current - created_at >= CHAT_SESSION_TTL_SECONDS
            ):
                expired.append(sid)
        for sid in expired:
            store.pop(sid, None)

def _store_chat_session(store: dict[str, dict], session_id: str, session: dict) -> None:
    _purge_expired_chat_sessions()
    if not isinstance(session, dict) or not _valid_session_timestamp(session.get("created_at")):
        raise ValueError("Chat sessions require a finite numeric created_at timestamp.")

    all_stores = (_TFIDF_SESSIONS, _SEMANTIC_SESSIONS)
    valid_sessions = []
    for target in all_stores:
        for sid, data in list(target.items()):
            created_at = data.get("created_at") if isinstance(data, dict) else None
            if not _valid_session_timestamp(created_at):
                # Malformed entries must not crash eviction or consume capacity.
                target.pop(sid, None)
                continue
            valid_sessions.append((sid, data, target))

    total = sum(len(target) for target in all_stores)
    if total >= MAX_CHAT_SESSIONS and valid_sessions:
        oldest_sid, _, oldest_store = min(
            valid_sessions, key=lambda item: item[1]["created_at"]
        )
        oldest_store.pop(oldest_sid, None)
    store[session_id] = session

def _authorized_session_org(session_org_id: str, org_id: str) -> bool:
    return session_org_id == org_id


def _session_is_usable(session: object, *, semantic: bool) -> bool:
    if not isinstance(session, dict):
        return False
    if not all(isinstance(session.get(key), str) and session.get(key) for key in ("org_id", "user_id", "filename")):
        return False
    if not _valid_session_timestamp(session.get("created_at")):
        return False
    if not semantic and not isinstance(session.get("index"), dict):
        return False
    return True


async def _read_upload_limited(file: UploadFile) -> bytes:
    # Read at most one byte beyond the configured limit so oversized uploads
    # are rejected without first buffering an unbounded request body in memory.
    file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, detail="Uploaded document exceeds the 10 MB limit.")
    return file_bytes


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

    file_bytes = await _read_upload_limited(file)
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
        _store_chat_session(_SEMANTIC_SESSIONS, session_id, {
            "filename": file.filename, "org_id": str(org_uuid), "user_id": str(user_uuid), "created_at": time.time(),
        })
        return {"session_id": session_id, "filename": file.filename, "chunk_count": len(chunks), "mode": "semantic"}

    session_id = str(uuid.uuid4())
    _store_chat_session(_TFIDF_SESSIONS, session_id, {
        "filename": file.filename, "index": build_index(chunks), "org_id": str(org_uuid),
        "user_id": str(user_uuid), "created_at": time.time(),
    })
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
    user_id: str = Depends(require_permission("chat", "view")),
):
    try:
        session_uuid = uuid.UUID(str(req.session_id))
        org_uuid = uuid.UUID(str(org_id))
        user_uuid = uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid session, organization, or user identifier.") from exc

    _purge_expired_chat_sessions()
    filename = None
    matches: list[dict] = []

    if str(session_uuid) in _SEMANTIC_SESSIONS:
        session = _SEMANTIC_SESSIONS[str(session_uuid)]
        if not _session_is_usable(session, semantic=True):
            _SEMANTIC_SESSIONS.pop(str(session_uuid), None)
            raise HTTPException(404, detail="Session is malformed or expired. Upload the document again.")
        if not _authorized_session_org(session["org_id"], str(org_uuid)):
            raise HTTPException(403, detail="Document does not belong to this organization.")
        if session["user_id"] != str(user_uuid):
            raise HTTPException(403, detail="Document session does not belong to this user.")
        from app.models.document import Document
        doc_uuid = session_uuid
        doc = db.query(Document).filter(Document.id == doc_uuid, Document.org_id == org_uuid).first()
        if not doc:
            raise HTTPException(404, detail="Document session not found.")
        filename = session["filename"]
        query_embedding = get_query_embedding(req.question)
        matches = semantic_retrieve(db, doc_uuid, query_embedding, top_k=req.top_k)
    elif str(session_uuid) in _TFIDF_SESSIONS:
        session = _TFIDF_SESSIONS[str(session_uuid)]
        if not _session_is_usable(session, semantic=False):
            _TFIDF_SESSIONS.pop(str(session_uuid), None)
            raise HTTPException(404, detail="Session is malformed or expired. Upload the document again.")
        if not _authorized_session_org(session["org_id"], str(org_uuid)):
            raise HTTPException(403, detail="Document does not belong to this organization.")
        if session["user_id"] != str(user_uuid):
            raise HTTPException(403, detail="Document session does not belong to this user.")
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
