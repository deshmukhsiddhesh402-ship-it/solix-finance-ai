"""
Auth utilities: OTP generation/verification and JWT issuance.

OTP DELIVERY NOTE: this generates and validates OTP codes but does not send
them anywhere — wire `send_otp_via_email_or_sms()` to a real provider
(e.g. AWS SES/SNS, Twilio, MSG91 for Indian SMS) before going to production.
For local dev, the OTP is returned directly in the API response so you can
test the flow without a real email/SMS provider configured.
"""
import random
import string
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.config import settings

# email -> {"otp": str, "expires_at": datetime}
# Production: move to Redis with a TTL instead of an in-memory dict.
_OTP_STORE: dict[str, dict] = {}


def generate_otp(email: str, length: int = 6, ttl_minutes: int = 10) -> str:
    otp = "".join(random.choices(string.digits, k=length))
    _OTP_STORE[email] = {
        "otp": otp,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    }
    return otp


def verify_otp(email: str, otp: str) -> bool:
    record = _OTP_STORE.get(email)
    if not record:
        return False
    if datetime.now(timezone.utc) > record["expires_at"]:
        del _OTP_STORE[email]
        return False
    if record["otp"] != otp:
        return False
    del _OTP_STORE[email]  # one-time use
    return True


def send_otp_via_email_or_sms(email: str, otp: str) -> None:
    """Stub — wire to a real provider (AWS SES/SNS, Twilio, MSG91) in
    production. Logging instead of sending keeps local dev unblocked."""
    print(f"[DEV ONLY] OTP for {email}: {otp}")


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        return None
