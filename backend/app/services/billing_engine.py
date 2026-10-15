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
import logging

logger = logging.getLogger(__name__)


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



# ---------------------------------------------------------------------------
# Atomic monthly usage metering
# ---------------------------------------------------------------------------
_USAGE_COUNTERS = {
    "ai_chat_uploads_this_month": "ai_chat_uploads_per_month",
    "invoice_ocr_this_month": "invoice_ocr_per_month",
}


def _current_usage_period_start(now=None):
    """Return the UTC start of the current calendar month."""
    from datetime import datetime, timezone
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def check_and_consume_usage(db, org_id, usage_key: str, *, consume: bool = True, now=None) -> dict:
    """Check/reset a monthly quota and optionally consume one unit atomically.

    PostgreSQL row locking serializes requests for one organization, so two
    uploads cannot both consume the final available unit. Missing subscriptions
    are initialized on the trial plan. Callers should release the reservation
    if downstream persistence fails.
    """
    from sqlalchemy import text
    limit_key = _USAGE_COUNTERS.get(usage_key)
    if not limit_key:
        raise ValueError("Unsupported usage key.")
    period_start = _current_usage_period_start(now)
    params = {"org_id": str(org_id), "period_start": period_start}
    db.execute(text(
        "INSERT INTO subscriptions (org_id, plan, status, usage_period_start) "
        "VALUES (:org_id, 'trial', 'active', :period_start) "
        "ON CONFLICT (org_id) DO NOTHING"
    ), params)
    row = db.execute(text(
        f"SELECT plan, status, current_period_end, usage_period_start, {usage_key} FROM subscriptions "
        "WHERE org_id = :org_id FOR UPDATE"
    ), params).mappings().one()
    from datetime import datetime, timezone
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    else:
        current_time = current_time.astimezone(timezone.utc)
    plan = row["plan"] if row["plan"] in PLANS else "trial"
    if plan != "trial" and (
        row["status"] != "active"
        or row["current_period_end"] is None
        or row["current_period_end"] <= current_time
    ):
        plan = "trial"
    previous_period = row["usage_period_start"]
    current_usage = int(row[usage_key] or 0)
    # Reset for any non-current anchor, including malformed/future values.
    # A future anchor must not preserve stale counters indefinitely.
    period_reset = previous_period is None or previous_period != period_start
    if period_reset:
        current_usage = 0
        db.execute(text(
            "UPDATE subscriptions SET ai_chat_uploads_this_month = 0, "
            "invoice_ocr_this_month = 0, usage_period_start = :period_start, updated_at = now() "
            "WHERE org_id = :org_id"
        ), params)
    limit = get_plan_limits(plan).get(limit_key)
    allowed = limit is None or current_usage < limit
    if consume and allowed:
        current_usage += 1
        db.execute(text(
            f"UPDATE subscriptions SET {usage_key} = :current_usage, usage_period_start = :period_start, updated_at = now() "
            "WHERE org_id = :org_id"
        ), {**params, "current_usage": current_usage})
    db.commit()
    return {
        "plan": plan, "usage_key": usage_key, "current_usage": current_usage,
        "limit": limit, "allowed": allowed, "consumed": bool(consume and allowed),
    }


def release_usage(db, org_id, usage_key: str, *, now=None) -> None:
    """Release a reserved unit after downstream failure, without crossing months."""
    from sqlalchemy import text
    if usage_key not in _USAGE_COUNTERS:
        raise ValueError("Unsupported usage key.")
    db.execute(text(
        f"UPDATE subscriptions SET {usage_key} = GREATEST({usage_key} - 1, 0), updated_at = now() "
        "WHERE org_id = :org_id AND usage_period_start = :period_start"
    ), {"org_id": str(org_id), "period_start": _current_usage_period_start(now)})
    db.commit()

def release_usage_after_failure(db, org_id, usage_key: str, *, now=None) -> bool:
    """Best-effort quota compensation that preserves the original failure.

    A downstream upload/OCR error should remain the error returned to the caller
    even if the compensation transaction also fails. The failure is logged so
    quota drift is visible to operators instead of being silently ignored.
    """
    try:
        release_usage(db, org_id, usage_key, now=now)
        return True
    except Exception:
        logger.exception(
            "Failed to release reserved %s usage after downstream failure for org %s",
            usage_key,
            org_id,
        )
        return False


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
