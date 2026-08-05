"""
Module: Subscription Billing (Razorpay) — API layer.

Requires RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, and RAZORPAY_WEBHOOK_SECRET
in backend/.env (see .env.example). The actual Razorpay API call to create
an order needs the `razorpay` Python SDK and live network access to
api.razorpay.com — not testable in this sandbox. What IS tested: the
webhook/payment signature verification and plan-gating logic underneath
(see app/services/billing_engine.py and its accompanying test run).
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings
from app.services.billing_engine import (
    PLANS, build_order_payload, verify_webhook_signature, verify_payment_signature,
    is_within_limit,
)

router = APIRouter()


@router.get("/plans")
def list_plans():
    """Public — powers the pricing page."""
    return {"plans": PLANS}


class CreateOrderRequest(BaseModel):
    org_id: str
    plan: str


@router.post("/create-order")
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)):
    """Create a Razorpay order for the checkout flow. The frontend takes the
    returned order_id and opens Razorpay's Checkout widget with it; on
    success, Razorpay calls back to /verify-payment below.
    """
    try:
        payload = build_order_payload(req.plan, req.org_id)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(
            503,
            detail="Razorpay is not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in backend/.env.",
        )

    import razorpay  # local import: only needed on this path, and only installed for production use

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order = client.order.create(data=payload)
    return {"order_id": order["id"], "amount": order["amount"], "currency": order["currency"], "key_id": settings.RAZORPAY_KEY_ID}


class VerifyPaymentRequest(BaseModel):
    org_id: str
    plan: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/verify-payment")
def verify_payment(req: VerifyPaymentRequest, db: Session = Depends(get_db)):
    """Called by the frontend immediately after Razorpay Checkout succeeds.
    CRITICAL: never activate a plan without verifying this signature first —
    otherwise anyone could POST fake payment IDs and get free access.
    """
    if not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(503, detail="Razorpay is not configured.")

    valid = verify_payment_signature(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature, settings.RAZORPAY_KEY_SECRET,
    )
    if not valid:
        raise HTTPException(400, detail="Payment signature verification failed — this payment cannot be trusted.")

    from app.models.billing import Subscription

    sub = db.query(Subscription).filter(Subscription.org_id == req.org_id).first()
    period_end = datetime.now(timezone.utc) + timedelta(days=30)
    if sub:
        sub.plan = req.plan
        sub.status = "active"
        sub.razorpay_order_id = req.razorpay_order_id
        sub.razorpay_payment_id = req.razorpay_payment_id
        sub.current_period_end = period_end
    else:
        sub = Subscription(
            org_id=req.org_id, plan=req.plan, status="active",
            razorpay_order_id=req.razorpay_order_id, razorpay_payment_id=req.razorpay_payment_id,
            current_period_end=period_end,
        )
        db.add(sub)
    db.commit()
    return {"message": f"Subscription activated: {req.plan}", "current_period_end": period_end.isoformat()}


@router.post("/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Server-to-server webhook from Razorpay (configure this URL in the
    Razorpay dashboard). Handles cases the client-side verify-payment flow
    might miss — e.g. subscription renewals, failed recurring charges.
    """
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(503, detail="Razorpay webhook secret is not configured.")

    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(raw_body.decode("utf-8"), signature, settings.RAZORPAY_WEBHOOK_SECRET):
        raise HTTPException(400, detail="Webhook signature verification failed.")

    payload = await request.json()
    event = payload.get("event", "")

    from app.models.billing import Subscription

    if event == "payment.failed":
        org_id = payload.get("payload", {}).get("payment", {}).get("entity", {}).get("notes", {}).get("org_id")
        if org_id:
            sub = db.query(Subscription).filter(Subscription.org_id == org_id).first()
            if sub:
                sub.status = "past_due"
                db.commit()

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Usage gating — call this from other routers before a metered action
# ---------------------------------------------------------------------------
@router.get("/check-limit")
def check_limit(
    org_id: str = Query(...), usage_key: str = Query(...), db: Session = Depends(get_db),
):
    """Other routers (chat.py, invoice_ocr.py) should call this before
    letting a metered action (AI Chat upload, invoice OCR) proceed. Not yet
    wired into those routers in this pass — see README caveat."""
    from app.models.billing import Subscription

    sub = db.query(Subscription).filter(Subscription.org_id == org_id).first()
    plan = sub.plan if sub else "trial"
    current_usage = 0
    if sub:
        current_usage = getattr(sub, usage_key, 0) or 0

    allowed = is_within_limit(plan, usage_key, current_usage)
    return {"plan": plan, "usage_key": usage_key, "current_usage": current_usage, "allowed": allowed}
