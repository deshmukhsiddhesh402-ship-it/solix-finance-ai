"""
ORM models for the Accounting module's persisted data — mirrors the
`organizations`, `chart_of_accounts`, `journal_entries`, and `journal_lines`
tables in database/schema.sql. This is what makes the Dashboard "live":
previously, /api/accounting endpoints were stateless (you POSTed lines and
got a computed result back, nothing saved). These models let entries
actually persist so the dashboard can query real historical data.
"""
import uuid
from datetime import date as date_type
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Date, Numeric, func, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    gstin = Column(String(15), nullable=True)
    pan = Column(String(10), nullable=True)
    plan = Column(String(20), nullable=False, default="trial")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    accounts = relationship("ChartOfAccount", back_populates="organization")
    journal_entries = relationship("JournalEntry", back_populates="organization")


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    code = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    account_type = Column(String(20), nullable=False)  # asset, liability, equity, income, expense
    parent_id = Column(UUID(as_uuid=True), ForeignKey("chart_of_accounts.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    organization = relationship("Organization", back_populates="accounts")


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    entry_date = Column(Date, nullable=False)
    narration = Column(Text, nullable=True)
    reference_no = Column(String(50), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="journal_entries")
    lines = relationship("JournalLine", back_populates="journal_entry", cascade="all, delete-orphan")


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    journal_id = Column(UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="CASCADE"))
    account_id = Column(UUID(as_uuid=True), ForeignKey("chart_of_accounts.id"))
    debit = Column(Numeric(18, 2), nullable=False, default=0)
    credit = Column(Numeric(18, 2), nullable=False, default=0)

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("ChartOfAccount")
