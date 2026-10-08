"""
ORM models for authentication and tenant membership.

The database schema remains the source of truth. These models cover only the
authentication rows needed by the OTP flow and tenant-aware authorization.
"""
import uuid

from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

# Canonical tenant membership mapping shared by auth and enterprise authorization.
from app.models.enterprise import OrgMembership

Base = declarative_base()


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    auth_provider = Column(String(20), nullable=False, default="otp")
    role = Column(String(20), nullable=False, default="accountant")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


