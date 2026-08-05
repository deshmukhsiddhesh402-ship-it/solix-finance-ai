"""
ORM model for the `users` table (schema.sql). Previously only referenced
via raw SQL in schema.sql — no SQLAlchemy model existed because the OTP
auth flow (auth.py) didn't persist users, it just issued JWTs. Enterprise
features (org membership, audit logs) need a real user row to attach to,
so this is now a proper model.
"""
import uuid
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)  # primary/default org; multi-org membership is in org_memberships
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    auth_provider = Column(String(20), nullable=False, default="otp")  # google, microsoft, otp
    role = Column(String(20), nullable=False, default="accountant")     # legacy/default role
    created_at = Column(DateTime(timezone=True), server_default=func.now())
