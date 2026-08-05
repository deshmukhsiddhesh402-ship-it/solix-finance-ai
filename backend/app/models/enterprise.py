"""
ORM models for Enterprise Features: multi-company membership (a user can
belong to several organizations with a different role in each), audit
logs, API keys, scheduled reports, and notifications.
"""
import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, Boolean, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class OrgMembership(Base):
    """A user's role within a specific organization — this is what makes
    multi-company support real: the same user can be Admin in one company
    and Auditor in another, rather than one global role per user."""
    __tablename__ = "org_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, default="accountant")  # admin, accountant, auditor
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(20), nullable=False)          # create, edit, delete, approve, login, etc.
    entity_type = Column(String(50), nullable=False)     # journal_entry, invoice, user, ...
    entity_id = Column(String(100), nullable=True)
    changes = Column(JSON, nullable=True)                 # output of audit_engine.diff_fields
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)            # human label, e.g. "Zapier integration"
    hashed_key = Column(String(64), nullable=False, unique=True)  # sha256 hex digest
    key_prefix_display = Column(String(30), nullable=False)       # masked, for UI display only
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked = Column(Boolean, default=False)


class ScheduledReport(Base):
    """Data model for scheduled reports. NOTE: creating a row here does not
    itself schedule anything — actual execution needs a background worker
    (e.g. Celery beat, already in the stack via Redis) polling this table
    and calling report_export_engine.py at the right time. Not wired up in
    this pass — see the honesty note in README.md."""
    __tablename__ = "scheduled_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(String(30), nullable=False)      # dashboard_pdf, dashboard_excel, gst_summary, ...
    frequency = Column(String(20), nullable=False)        # daily, weekly, monthly
    recipient_emails = Column(JSON, nullable=False)        # list[str]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_sent_at = Column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    """In-app notification record. NOTE: this stores notifications for
    display in-app; it does not itself send email/SMS/push — wire a real
    provider (SES/SNS, Twilio, FCM) if out-of-app delivery is needed,
    same caveat as the OTP module in security.py."""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
