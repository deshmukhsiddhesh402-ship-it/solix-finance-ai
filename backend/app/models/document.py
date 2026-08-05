"""
ORM models for the AI Chat / RAG module. These map directly onto the
`documents` and `document_chunks` tables defined in database/schema.sql —
keep the two in sync if you change one.
"""
import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

from app.services.embedding_service import EMBEDDING_DIMENSIONS

Base = declarative_base()


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)  # nullable for single-tenant/demo use
    uploaded_by = Column(UUID(as_uuid=True), nullable=True)
    file_name = Column(String(255))
    file_type = Column(String(20))  # pdf, xlsx, docx, txt
    storage_path = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS), nullable=True)

    document = relationship("Document", back_populates="chunks")
