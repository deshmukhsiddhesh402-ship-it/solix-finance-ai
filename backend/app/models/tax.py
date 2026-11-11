"""ORM mapping for persisted Indian tax return records in database/schema.sql."""
import uuid
from sqlalchemy import Column, String, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class GSTReturn(Base):
    __tablename__ = "gst_returns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    return_type = Column(String(10), nullable=False)
    period = Column(String(7), nullable=False)
    total_taxable_value = Column(Numeric(18, 2), nullable=True)
    total_tax_liability = Column(Numeric(18, 2), nullable=True)
    filed_at = Column(DateTime(timezone=True), nullable=True)


class TDSEntry(Base):
    __tablename__ = "tds_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    section = Column(String(10), nullable=False)
    deductee_name = Column(String(255), nullable=True)
    deductee_pan = Column(String(10), nullable=True)
    amount_paid = Column(Numeric(18, 2), nullable=False)
    tds_rate = Column(Numeric(5, 2), nullable=False)
    tds_amount = Column(Numeric(18, 2), nullable=False)
    deposit_date = Column(Date, nullable=True)
