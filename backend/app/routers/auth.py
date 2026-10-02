"""Email OTP login endpoints consumed by the frontend's NextAuth provider."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    generate_otp, verify_otp, discard_otp,
    send_otp_via_email_or_sms, create_access_token,
)
from app.core.db import get_db

router = APIRouter()


class OtpRequestBody(BaseModel):
    email: EmailStr


@router.post("/otp/request")
def request_otp(req: OtpRequestBody):
    try:
        otp = generate_otp(str(req.email))
    except ValueError as exc:
        raise HTTPException(429, detail="Please wait before requesting another OTP.") from exc

    try:
        send_otp_via_email_or_sms(str(req.email), otp)
    except RuntimeError as exc:
        discard_otp(str(req.email))
        raise HTTPException(503, detail="OTP delivery is not configured.") from exc

    response = {"message": "If the address is eligible, an OTP will be sent."}
    if settings.ENV.strip().lower() in {"development", "dev"}:
        response["dev_otp"] = otp
    return response


class OtpVerifyBody(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=8, pattern=r"^[0-9]{6,8}$")


@router.post("/otp/verify")
def verify_otp_endpoint(req: OtpVerifyBody, db: Session = Depends(get_db)):
    if not verify_otp(str(req.email), req.otp):
        raise HTTPException(401, detail="Invalid or expired OTP")

    from app.models.auth_user import User

    user = db.query(User).filter(User.email == str(req.email)).first()
    if not user:
        user = User(email=str(req.email), full_name=str(req.email).split("@")[0], auth_provider="otp")
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(subject=str(req.email))
    return {"user_id": str(user.id), "full_name": user.full_name, "access_token": token}
