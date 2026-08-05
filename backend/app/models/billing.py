"""
ORM model for subscription/billing state per organization.
"""
import uuid
from sqlalchemy import Column, String, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    plan = Column(String(20), nullable=False, default="trial")  # trial, pro, enterprise
    status = Column(String(20), nullable=False, default="active")  # active, past_due, cancelled
    razorpay_order_id = Column(String(100), nullable=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    ai_chat_uploads_this_month = Column(Integer, nullable=False, default=0)
    invoice_ocr_this_month = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
