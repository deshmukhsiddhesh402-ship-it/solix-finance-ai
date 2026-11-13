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
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Date, Numeric, func, Boolean, Integer, BigInteger, Identity
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


class FixedAsset(Base):
    __tablename__ = "fixed_assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    asset_name = Column(String(255), nullable=False)
    purchase_date = Column(Date, nullable=False)
    cost = Column(Numeric(18, 2), nullable=False)
    salvage_value = Column(Numeric(18, 2), nullable=False, default=0)
    useful_life_years = Column(Integer, nullable=False)
    depreciation_method = Column(String(20), nullable=False, default="straight_line")


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"))
    sku = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    costing_method = Column(String(10), nullable=False, default="FIFO")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("inventory_items.id", ondelete="CASCADE"))
    txn_type = Column(String(10), nullable=False)
    txn_date = Column(Date, nullable=False)
    quantity = Column(Numeric(18, 4), nullable=False)
    unit_cost = Column(Numeric(18, 4), nullable=True)
    sequence_no = Column(BigInteger, Identity(always=True), nullable=False)
    reference_no = Column(String(100), nullable=True)


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
    gst_rate_pct = Column(Numeric(5, 2), nullable=True)
    gst_type = Column(String(10), nullable=True)
    gst_taxable_value = Column(Numeric(18, 2), nullable=True)
    tds_section = Column(String(10), nullable=True)
    tds_rate = Column(Numeric(5, 2), nullable=True)
    tds_amount = Column(Numeric(18, 2), nullable=True)

    journal_entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("ChartOfAccount")
