"""Module: Subscription Billing (Razorpay) — tenant-authorized API."""
from datetime import datetime, timedelta, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from app.services.billing_engine import (
    PLANS, build_order_payload, verify_webhook_signature, verify_payment_signature,
    validate_gateway_payment, is_within_limit,
)
from app.routers.enterprise import require_permission

router = APIRouter()


@router.get("/plans")
def list_plans():
    return {"plans": PLANS}


class CreateOrderRequest(BaseModel):
    org_id: str
    plan: str


@router.post("/create-order")
def create_order(
    req: CreateOrderRequest,
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("billing", "create")),
):
    if req.org_id != org_id:
        raise HTTPException(400, detail="Request organization must match the authorized organization.")
    try:
        org_uuid = uuid.UUID(org_id)
        payload = build_order_payload(req.plan, str(org_uuid))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization or plan.") from exc

    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, detail="Razorpay is not configured.")

    import razorpay
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order = client.order.create(data=payload)
    return {"order_id": order["id"], "amount": order["amount"], "currency": order["currency"], "key_id": settings.RAZORPAY_KEY_ID}


class VerifyPaymentRequest(BaseModel):
    org_id: str
    plan: str
    razorpay_order_id: str = Field(min_length=1, max_length=100)
    razorpay_payment_id: str = Field(min_length=1, max_length=100)
    razorpay_signature: str = Field(min_length=64, max_length=128)


@router.post("/verify-payment")
def verify_payment(
    req: VerifyPaymentRequest,
    org_id: str = Query(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("billing", "create")),
):
    if req.org_id != org_id:
        raise HTTPException(400, detail="Request organization must match the authorized organization.")
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc

    if req.plan not in PLANS or PLANS[req.plan]["price_inr_per_month"] <= 0:
        raise HTTPException(400, detail="Invalid paid plan.")
    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, detail="Razorpay is not configured.")

    if not verify_payment_signature(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature, settings.RAZORPAY_KEY_SECRET,
    ):
        raise HTTPException(400, detail="Payment signature verification failed — this payment cannot be trusted.")

    import razorpay
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        gateway_order = client.order.fetch(req.razorpay_order_id)
        gateway_payment = client.payment.fetch(req.razorpay_payment_id)
    except Exception as exc:
        raise HTTPException(502, detail="Payment could not be verified with the payment provider.") from exc

    try:
        validate_gateway_payment(
            gateway_order,
            gateway_payment,
            req.razorpay_order_id,
            req.razorpay_payment_id,
            str(org_uuid),
            req.plan,
        )
    except ValueError as exc:
        raise HTTPException(400, detail="Payment details do not match the requested organization or plan.") from exc

    from app.models.billing import Subscription

    # Payment IDs are globally unique at the gateway. Treat a previously
    # recorded payment as idempotent only when its tenant/order/plan binding
    # is identical; never let a payment be replayed across organizations.
    existing_payment = (
        db.query(Subscription)
        .filter(Subscription.razorpay_payment_id == req.razorpay_payment_id)
        .first()
    )
    if existing_payment:
        if existing_payment.org_id != org_uuid:
            raise HTTPException(409, detail="Payment has already been associated with another organization.")
        if existing_payment.razorpay_order_id != req.razorpay_order_id or existing_payment.plan != req.plan:
            raise HTTPException(409, detail="Payment has already been associated with a different order or plan.")
        return {
            "message": f"Subscription already activated: {existing_payment.plan}",
            "current_period_end": existing_payment.current_period_end.isoformat()
            if existing_payment.current_period_end else None,
        }

    sub = db.query(Subscription).filter(Subscription.org_id == org_uuid).first()
    period_end = datetime.now(timezone.utc) + timedelta(days=30)
    if sub:
        sub.plan = req.plan
        sub.status = "active"
        sub.razorpay_order_id = req.razorpay_order_id
        sub.razorpay_payment_id = req.razorpay_payment_id
        sub.current_period_end = period_end
    else:
        sub = Subscription(
            org_id=org_uuid, plan=req.plan, status="active",
            razorpay_order_id=req.razorpay_order_id, razorpay_payment_id=req.razorpay_payment_id,
            current_period_end=period_end,
        )
        db.add(sub)
    db.commit()
    return {"message": f"Subscription activated: {req.plan}", "current_period_end": period_end.isoformat()}


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    MAX_WEBHOOK_BODY_BYTES = 1_000_000
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(503, detail="Razorpay webhook secret is not configured.")
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(413, detail="Webhook payload is too large.")
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        payload_text = raw_body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, detail="Webhook payload is not valid UTF-8.") from exc
    if not verify_webhook_signature(payload_text, signature, settings.RAZORPAY_WEBHOOK_SECRET):
        raise HTTPException(400, detail="Webhook signature verification failed.")

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(400, detail="Webhook payload is not valid JSON.") from exc
    event = payload.get("event", "")
    from app.models.billing import Subscription

    if event == "payment.failed":
        org_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes", {}).get("org_id")
        try:
            org_uuid = uuid.UUID(str(org_id))
        except (ValueError, AttributeError, TypeError):
            org_uuid = None
        if org_uuid:
            sub = db.query(Subscription).filter(Subscription.org_id == org_uuid).first()
            if sub:
                sub.status = "past_due"
                db.commit()
    return {"status": "ok"}


@router.get("/check-limit")
def check_limit(
    org_id: str = Query(...),
    usage_key: str = Query(...),
    db: Session = Depends(get_db),
    _user: str = Depends(require_permission("billing", "view")),
):
    allowed_keys = {"ai_chat_uploads_this_month", "invoice_ocr_this_month"}
    if usage_key not in allowed_keys:
        raise HTTPException(400, detail="Unsupported usage key.")
    try:
        org_uuid = uuid.UUID(org_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(400, detail="Invalid organization identifier.") from exc

    from app.models.billing import Subscription
    sub = db.query(Subscription).filter(Subscription.org_id == org_uuid).first()
    plan = sub.plan if sub else "trial"
    current_usage = getattr(sub, usage_key, 0) or 0 if sub else 0
    allowed = is_within_limit(plan, usage_key.replace("_this_month", "_per_month"), current_usage)
    return {"plan": plan, "usage_key": usage_key, "current_usage": current_usage, "allowed": allowed}
