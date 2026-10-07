"""Authentication helpers for OTP verification and signed access tokens.

OTP delivery is intentionally fail-closed outside development until a real
email/SMS provider is configured. The in-memory store is suitable only for
single-process development; production must use a shared store and provider.
"""
import hmac
import secrets
import string
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.config import settings

MAX_OTP_ATTEMPTS = 5
OTP_RESEND_SECONDS = 60
_OTP_STORE: dict[str, dict] = {}
_OTP_LAST_SENT: dict[str, datetime] = {}
MAX_OTP_TRACKED_EMAILS = 10000

def _purge_expired_otp_records(now: datetime) -> None:
    expired = [
        key for key, record in _OTP_STORE.items()
        if now >= record["expires_at"]
    ]
    for key in expired:
        _OTP_STORE.pop(key, None)

    stale_cooldowns = [
        key for key, sent_at in _OTP_LAST_SENT.items()
        if now - sent_at >= timedelta(seconds=OTP_RESEND_SECONDS)
        and key not in _OTP_STORE
    ]
    for key in stale_cooldowns:
        _OTP_LAST_SENT.pop(key, None)



def _email_key(email: str) -> str:
    return email.strip().lower()


def generate_otp(email: str, length: int = 6, ttl_minutes: int = 10) -> str:
    """Create a cryptographically random OTP with resend and expiry limits."""
    if not 6 <= length <= 8:
        raise ValueError("OTP length must be between 6 and 8 digits.")
    if ttl_minutes <= 0:
        raise ValueError("OTP expiry must be positive.")

    key = _email_key(email)
    now = datetime.now(timezone.utc)
    _purge_expired_otp_records(now)
    if len(_OTP_STORE) >= MAX_OTP_TRACKED_EMAILS and key not in _OTP_STORE:
        oldest = min(_OTP_STORE, key=lambda k: _OTP_STORE[k]["expires_at"])
        _OTP_STORE.pop(oldest, None)
    last_sent = _OTP_LAST_SENT.get(key)
    if last_sent and now - last_sent < timedelta(seconds=OTP_RESEND_SECONDS):
        raise ValueError("Please wait before requesting another OTP.")

    otp = "".join(secrets.choice(string.digits) for _ in range(length))
    _OTP_STORE[key] = {
        "otp": otp,
        "expires_at": now + timedelta(minutes=ttl_minutes),
        "attempts": 0,
    }
    _OTP_LAST_SENT[key] = now
    return otp


def discard_otp(email: str) -> None:
    """Discard an OTP when delivery fails; retain the resend cooldown."""
    _OTP_STORE.pop(_email_key(email), None)


def verify_otp(email: str, otp: str) -> bool:
    key = _email_key(email)
    record = _OTP_STORE.get(key)
    if not record:
        return False
    now = datetime.now(timezone.utc)
    if now >= record["expires_at"] or record["attempts"] >= MAX_OTP_ATTEMPTS:
        _OTP_STORE.pop(key, None)
        return False
    if not hmac.compare_digest(record["otp"], str(otp)):
        record["attempts"] += 1
        if record["attempts"] >= MAX_OTP_ATTEMPTS:
            _OTP_STORE.pop(key, None)
        return False
    _OTP_STORE.pop(key, None)  # one-time use
    return True


def send_otp_via_email_or_sms(email: str, otp: str) -> None:
    """No delivery provider is configured yet; never log or expose OTPs here."""
    if settings.ENV.strip().lower() in {"development", "dev"}:
        return
    raise RuntimeError("OTP delivery provider is not configured.")


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    if not subject:
        raise ValueError("Token subject is required.")
    minutes = settings.JWT_EXPIRE_MINUTES if expires_minutes is None else expires_minutes
    if minutes <= 0:
        raise ValueError("Token expiry must be positive.")
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": subject, "iat": datetime.now(timezone.utc), "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if not payload.get("sub"):
            return None
        return payload
    except Exception:
        return None
