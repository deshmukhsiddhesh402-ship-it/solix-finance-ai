"""
Module: Subscription Billing (Razorpay) — chosen for Indian CA
firms/businesses since it natively supports UPI, netbanking, and cards
domestically, unlike Stripe which is card/international-first.

SECURITY-CRITICAL PIECE: Razorpay webhook signature verification. Razorpay
signs every webhook payload with HMAC-SHA256 using your webhook secret;
verifying it is what stops an attacker from POSTing a fake "payment
succeeded" event to your webhook endpoint and getting free access. This is
real, tested crypto — not a stub.
"""
import hmac
import hashlib


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------
PLANS = {
    "trial": {
        "label": "Trial", "price_inr_per_month": 0, "duration_days": 14,
        "limits": {"ai_chat_uploads_per_month": 10, "invoice_ocr_per_month": 20, "users": 2},
    },
    "pro": {
        "label": "Pro", "price_inr_per_month": 2999,
        "limits": {"ai_chat_uploads_per_month": 200, "invoice_ocr_per_month": 500, "users": 10},
    },
    "enterprise": {
        "label": "Enterprise", "price_inr_per_month": 9999,
        "limits": {"ai_chat_uploads_per_month": None, "invoice_ocr_per_month": None, "users": None},  # None = unlimited
    },
}


def get_plan_limits(plan: str) -> dict:
    return PLANS.get(plan, PLANS["trial"])["limits"]


def is_within_limit(plan: str, usage_key: str, current_usage: int) -> bool:
    """Check whether the org is still within its plan's usage limit for a
    given metered feature. A limit of None means unlimited."""
    limits = get_plan_limits(plan)
    limit = limits.get(usage_key)
    if limit is None:
        return True
    return current_usage < limit


# ---------------------------------------------------------------------------
# Razorpay order creation (subscription checkout)
# ---------------------------------------------------------------------------
def build_order_payload(plan: str, org_id: str) -> dict:
    """Build the payload for Razorpay's Orders API (POST /v1/orders).
    Amount is in paise (smallest currency unit) per Razorpay's convention.
    """
    plan_info = PLANS.get(plan)
    if not plan_info or plan_info["price_inr_per_month"] == 0:
        raise ValueError(f"Plan '{plan}' is not a paid plan or does not exist.")

    amount_paise = plan_info["price_inr_per_month"] * 100
    return {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"solix_{org_id}_{plan}",
        "notes": {"org_id": org_id, "plan": plan},
    }


# ---------------------------------------------------------------------------
# Webhook signature verification — SECURITY CRITICAL, real HMAC-SHA256
# ---------------------------------------------------------------------------
def verify_webhook_signature(payload_body: str, received_signature: str, webhook_secret: str) -> bool:
    """Verify a Razorpay webhook's X-Razorpay-Signature header.
    Per Razorpay's documented scheme: signature = HMAC-SHA256(payload_body, webhook_secret).
    Uses constant-time comparison to avoid timing side-channel leakage.
    """
    expected_signature = hmac.new(
        key=webhook_secret.encode("utf-8"),
        msg=payload_body.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, received_signature)


def verify_payment_signature(order_id: str, payment_id: str, received_signature: str, key_secret: str) -> bool:
    """Verify the signature returned to the CLIENT after a successful
    checkout (razorpay_order_id + razorpay_payment_id + razorpay_signature).
    Per Razorpay's documented scheme: signature = HMAC-SHA256(f"{order_id}|{payment_id}", key_secret).
    This is a DIFFERENT signature scheme from the webhook one above — the
    message format and which secret is used both differ, so don't reuse
    verify_webhook_signature for this.
    """
    message = f"{order_id}|{payment_id}"
    expected_signature = hmac.new(
        key=key_secret.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, received_signature)


def validate_gateway_payment(
    order: dict,
    payment: dict,
    order_id: str,
    payment_id: str,
    org_id: str,
    plan: str,
) -> None:
    """Validate gateway-side order/payment state against Solix's trusted intent."""
    plan_info = PLANS.get(plan)
    if not plan_info or plan_info["price_inr_per_month"] <= 0:
        raise ValueError("Invalid paid plan.")

    expected_amount = plan_info["price_inr_per_month"] * 100
    notes = order.get("notes")
    if not isinstance(notes, dict):
        raise ValueError("Razorpay order metadata is missing.")

    if str(order.get("id", "")) != order_id:
        raise ValueError("Razorpay order identifier mismatch.")
    if str(notes.get("org_id", "")) != org_id:
        raise ValueError("Razorpay order organization mismatch.")
    if str(notes.get("plan", "")) != plan:
        raise ValueError("Razorpay order plan mismatch.")
    if order.get("currency") != "INR" or order.get("amount") != expected_amount:
        raise ValueError("Razorpay order amount mismatch.")

    if str(payment.get("id", "")) != payment_id:
        raise ValueError("Razorpay payment identifier mismatch.")
    if str(payment.get("order_id", "")) != order_id:
        raise ValueError("Razorpay payment is not attached to this order.")
    if payment.get("currency") != "INR" or payment.get("amount") != expected_amount:
        raise ValueError("Razorpay payment amount mismatch.")
    if payment.get("status") != "captured":
        raise ValueError("Razorpay payment is not captured.")
